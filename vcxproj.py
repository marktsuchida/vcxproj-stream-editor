#!/bin/env python3

# Layout-preserving parser/manipulator/writer for Visual Studio 2010 projects


from collections import OrderedDict
import codecs
import io
import sys
import xml.parsers.expat
import xml.sax.saxutils


def main():
    project_filename = sys.argv[1]
    def gen_pipeline(line_writer):
        # Just echo for testing:
        return to_lines(compute_indent(to_strings(line_writer)))
    process_file_inplace(project_filename, gen_pipeline)


def process_file_inplace(filename, pipeline_gen):
    output = io.StringIO()
    handlers = XMLEventSource(pipeline_gen(line_writer(output)))
    parser = setup_parser(handlers)

    with open(filename, "rb") as input:
        try:
            parser.ParseFile(input)
        except xml.parsers.expat.ExpatError as err:
            print("Error:", xml.parsers.expat.errors.messages[err.code],
                  file=sys.stderr)

    with codecs.open(filename, "w", "utf-8-sig") as file:
        file.write(output.getvalue())


def setup_parser(handlers):
    parser = xml.parsers.expat.ParserCreate()

    parser.ordered_attributes = True
    parser.specified_attributes = True

    parser.StartElementHandler = handlers.start_element
    parser.EndElementHandler = handlers.end_element
    parser.CharacterDataHandler = handlers.characters

    return parser


class XMLStrings:
    @staticmethod
    def indent(n):
        return "  " * n

    @staticmethod
    def tag_open_elem(name, attrs):
        return "<{}{}>".format(name, XMLStrings._attrs(attrs))

    @staticmethod
    def tag_empty_elem(name, attrs):
        return "<{}{} />".format(name, XMLStrings._attrs(attrs))

    @staticmethod
    def tag_close_elem(name):
        return "</{}>".format(name)

    @staticmethod
    def _attrs(attrs):
        return "".join(" {}={}".format(name, xml.sax.saxutils.quoteattr(value))
                       for name, value in attrs.items())


def coroutine(genfunc):
    """Decorator for toplevel coroutines.

    Automatically primes coroutiens by calling next().
    """
    def wrapped(*args, **kwargs):
        generator = genfunc(*args, **kwargs)
        next(generator)
        return generator
    return wrapped


@coroutine
def logger(target, prefix="", writer=print):
    """A pass-through coroutine that prints items.

    (For debugging.)
    """
    while True:
        item = yield
        writer(prefix, item)
        target.send(item)


@coroutine
def line_writer(writer, newline="\r\n"):
    """Sink coroutine; writes strings as lines to writer.
    
    writer: writable file object
    input = string

    No newline is added at the end of the output.
    """
    line = yield
    writer.write(line)
    while True:
        line = yield
        writer.write(newline + line)


@coroutine
def to_strings(target):
    """Turn element-line items into strings.

    input = (indent_count, line_type, param_dict)
    output = string
    """
    target.send('<?xml version="1.0" encoding="utf-8"?>')
    while True:
        indent, action, params = yield
        if action == "start_elem_line":
            target.send(XMLStrings.indent(indent) +
                        XMLStrings.tag_open_elem(**params))
        elif action == "empty_elem_line":
            target.send(XMLStrings.indent(indent) +
                        XMLStrings.tag_empty_elem(**params))
        elif action == "content_elem_line":
            element_str = (XMLStrings.indent(indent) +
                           XMLStrings.tag_open_elem(name=params["name"],
                                                    attrs=params["attrs"]) +
                           params["content"] +
                           XMLStrings.tag_close_elem(name=params["name"]))
            # Content may contain newlines
            for line in element_str.split("\n"):
                target.send(line)
        elif action == "end_elem_line":
            target.send(XMLStrings.indent(indent) +
                        XMLStrings.tag_close_elem(**params))


@coroutine
def compute_indent(target):
    """Add indent count to line items.

    input = (line_type, param_dict)
    output = (indent_count, line_type, param_dict)
    """
    indent = 0
    try:
        while True:
            action, params = yield
            if action == "end_elem_line":
                indent -= 1
            target.send((indent, action, params))
            if action == "start_elem_line":
                indent += 1
    except GeneratorExit:
        target.close()


@coroutine
def to_lines(target):
    """Convert SAX event stream to line stream.

    input = (event_type, param_dict)
    output = (line_type, param_dict)
    """
    action, params = yield
    while True:
        if action == "start_elem":
            action, params = (yield from
                              to_lines_post_start_elem(target, **params))
            continue

        if action == "end_elem":
            target.send(("end_elem_line", params))
            action, params = yield
            continue

        action, params = yield


def to_lines_post_start_elem(target, **start_elem):
    """Sub-coroutine for to_lines().

    Returns the next (peeked) (action, params).
    """

    action, params = yield

    if action == "end_elem":
        assert params["name"] == start_elem["name"]
        target.send(("empty_elem_line", start_elem))
        return (yield)

    if action == "chars":
        return (yield from to_lines_elem_chars(target, start_elem, params))

    target.send(("start_elem_line", start_elem))
    return action, params


def to_lines_elem_chars(target, start_elem, chars):
    """Sub-coroutine for to_lines_post_start_elem().
    
    Returns the next (peeked) (action, params).
    """
    action, params = "chars", chars
    content = ""
    while action == "chars":
        content += params["content"]
        action, params = yield

    if action == "end_elem":
        assert params["name"] == start_elem["name"]
        target.send(("content_elem_line",
                     dict(name=start_elem["name"],
                          attrs=start_elem["attrs"],
                          content=content)))
        return (yield)

    assert not content.strip()
    target.send(("start_elem_line", start_elem))
    return action, params


class XMLEventSource:
    def __init__(self, target):
        self.target = target

    def start_element(self, name, attrs):
        # attrs is [name0, value0, name1, value1, ...]
        iattrs = iter(attrs)
        attr_items = zip(iattrs, iattrs)
        attrs = OrderedDict(attr_items)
        self.target.send(("start_elem", dict(name=name, attrs=attrs)))

    def end_element(self, name):
        self.target.send(("end_elem", dict(name=name)))

    def characters(self, content):
        self.target.send(("chars", dict(content=content)))


if __name__ == "__main__":
    main()
