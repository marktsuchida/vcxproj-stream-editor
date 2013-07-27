#!/bin/env python3

# Generic SAX-based parser/manipulator/writer for Visual Studio 2010 projects
#
# We prefer SAX over DOM because we want to be able to preserve attribute
# order. We convert the incoming event stream into a logical stream and back
# into xml.

import codecs
import io
import sys
import xml.sax
import xml.sax.handler
import xml.sax.saxutils


def main():
    project_filename = sys.argv[1]
    def gen_pipeline(line_writer):
        # Just echo for testing:
        return to_lines(logger(compute_indent(to_strings(line_writer)), "LOG:"))
    process_file_inplace(project_filename, gen_pipeline)


def process_file_inplace(filename, pipeline_gen):
    output = io.StringIO()
    handler = SAXEventSource(pipeline_gen(line_writer(output)))
    with codecs.open(filename, "r", "utf-8") as input:
        xml.sax.parse(input, handler)
    with codecs.open(filename, "w", "utf-8-sig") as file:
        file.write(output.getvalue())


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
def logger(target, prefix=""):
    """A pass-through coroutine that prints items."""
    while True:
        item = yield
        print(prefix, item)
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
def to_strings(target, newline="\r\n"):
    """Turn element-line items into strings.

    input = (indent_count, line_type, param_dict)
    output = string
    """
    target.send('<?xml version="1.0" encoding="utf-8"?>')
    try:
        while True:
            indent, action, params = yield
            if action == "start_elem_line":
                target.send(XMLStrings.indent(indent) +
                            XMLStrings.tag_open_elem(**params))
            elif action == "empty_elem_line":
                target.send(XMLStrings.indent(indent) +
                            XMLStrings.tag_empty_elem(**params))
            elif action == "content_elem_line":
                target.send(XMLStrings.indent(indent) +
                            XMLStrings.tag_open_elem(name=params["name"],
                                                     attrs=params["attrs"]) +
                            params["content"].replace("\n", newline) +
                            XMLStrings.tag_close_elem(name=params["name"]))
            elif action == "end_elem_line":
                target.send(XMLStrings.indent(indent) +
                            XMLStrings.tag_close_elem(**params))
    except GeneratorExit:
        target.close()


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
                print("dedent")
                indent -= 1
            target.send((indent, action, params))
            if action == "start_elem_line":
                print("indent")
                indent += 1
    except GeneratorExit:
        target.close()


@coroutine
def to_lines(target):
    """Convert SAX event stream to line stream.

    input = (event_type, param_dict)
    output = (line_type, param_dict)
    """
    try:
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

    except GeneratorExit:
        target.close()


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


class SAXEventSource(xml.sax.handler.ContentHandler):
    def __init__(self, target):
        self.target = target

    def startDocument(self):
        self.target.send(("start_doc", dict()))

    def endDocument(self):
        self.target.send(("end_doc", dict()))
        self.target.close()

    def startElement(self, name, attrs):
        self.target.send(("start_elem", dict(name=name, attrs=attrs)))

    def endElement(self, name):
        self.target.send(("end_elem", dict(name=name)))

    def characters(self, content):
        self.target.send(("chars", dict(content=content)))

    def ignorableWhitespace(self, whitespace):
        self.target.send(("space", dict(whitespace=whitespace)))


if __name__ == "__main__":
    main()
