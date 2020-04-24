# vcxproj-stream-editor
Simple Python library to parse Microsoft Visual Studio .vcxproj files and modify/rewrite without spurious changes

## Usage:

Given the following simplified `myproject.vcxproj`:
``` xml
<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup Label="Globals">
    <ProjectGuid>{96F21549-A7BF-4695-A1B1-B43625B91A14}</ProjectGuid>
  </PropertyGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">
    <ClCompile>
      <WarningLevel>Level3</WarningLevel>
    </ClCompile>
  </ItemDefinitionGroup>
</Project>
```

### Example 1 (input only):
``` python
import vcxproj

@vcxproj.coroutine
def print_project_guid():
    while True:
        action, params = yield
        if action == "start_elem" and params["name"] == "ProjectGuid":
            action, params = yield
            assert action == "chars"
            print("Project GUID is ", params["content"])

vcxproj.check_file("myproject.vcxproj", print_project_guid)
```
Output:
```
Project GUID is {96F21549-A7BF-4695-A1B1-B43625B91A14}
```

### Example 2 (input and output):
``` python
import vcxproj

@vcxproj.coroutine
def remove_warning_level(target)
    while True:
        action, params = yield
        if action == "start_elem" and params["name"] == "WarningLevel":
            action, params = yield
            assert action == "chars"
            action, params = yield
            assert action == "end_elem"
            assert params["name"] == "WarningLevel"
            continue
        target.send((action, params))
        
vcxproj.filter_file("myproject.vcxproj", remove_warning_level, "myproject.stripped.vcxproj")
```

`myproject.stripped.vcxproj` will have the following content:
``` xml
<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup Label="Globals">
    <ProjectGuid>{96F21549-A7BF-4695-A1B1-B43625B91A14}</ProjectGuid>
  </PropertyGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">
    <ClCompile>
    </ClCompile>
  </ItemDefinitionGroup>
</Project>
```

### Possible values for `(action, params)`:
| action       | params                                                               |
|--------------|----------------------------------------------------------------------|
| `start_elem` | `{"name":<elem_name>, "attrs":{<attr1>:<value1>, <attr2>:<value2>}}` |
| `chars`      | `{"content":<content>}`                                              |
| `end_elem`   | `{"name":<elem_name>}`                                               |
