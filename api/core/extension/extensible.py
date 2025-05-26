import enum
import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from core.helper.position_helper import sort_to_dict_by_position_map


"""
NOTE:
这个扩展系统的工作流程是：
1. 目录结构要求：
    - 每个扩展必须是一个子目录
    - 子目录中必须包含与目录名相同的 Python 文件
    - 非内置扩展必须包含 schema.json 配置文件
    - 内置扩展可以包含 __builtin__ 文件来指定显示位置
2. 扩展加载过程：
    - 扫描指定目录下的所有子目录
    - 检查每个子目录是否符合扩展要求
    - 动态加载扩展的 Python 模块
    - 查找继承自 Extensible 的扩展类
    - 加载扩展的配置信息
    - 创建扩展实例并返回
3. 扩展类型：
    - 内置扩展：系统自带的扩展，通过 __builtin__ 文件标识
    - 自定义扩展：用户添加的扩展，需要提供 schema.json 配置文件
4. 配置管理：
    - 通过 schema.json 定义扩展的配置表单
    - 支持扩展的标签和显示位置配置
    - 使用 Pydantic 进行数据验证
5. 这种设计使得系统可以：
    - 灵活地添加和移除扩展
    - 自动发现和加载扩展
    - 支持扩展的配置管理
    - 区分内置扩展和自定义扩展
    - 控制扩展的显示顺序
"""

class ExtensionModule(enum.Enum):
    MODERATION = "moderation"
    EXTERNAL_DATA_TOOL = "external_data_tool"


class ModuleExtension(BaseModel):
    extension_class: Any = None
    name: str
    label: Optional[dict] = None
    form_schema: Optional[list] = None
    builtin: bool = True
    position: Optional[int] = None


class Extensible:
    module: ExtensionModule

    name: str
    tenant_id: str
    config: Optional[dict] = None

    def __init__(self, tenant_id: str, config: Optional[dict] = None) -> None:
        self.tenant_id = tenant_id
        self.config = config

    @classmethod
    def scan_extensions(cls):
        extensions = []
        position_map: dict[str, int] = {}

        # get the path of the current class
        current_path = os.path.abspath(cls.__module__.replace(".", os.path.sep) + ".py")
        current_dir_path = os.path.dirname(current_path)

        # traverse subdirectories
        for subdir_name in os.listdir(current_dir_path):
            if subdir_name.startswith("__"):
                continue

            subdir_path = os.path.join(current_dir_path, subdir_name)
            extension_name = subdir_name
            if os.path.isdir(subdir_path):
                file_names = os.listdir(subdir_path)

                # is builtin extension, builtin extension
                # in the front-end page and business logic, there are special treatments.
                builtin = False
                # default position is 0 can not be None for sort_to_dict_by_position_map
                position = 0
                if "__builtin__" in file_names:
                    builtin = True

                    builtin_file_path = os.path.join(subdir_path, "__builtin__")
                    if os.path.exists(builtin_file_path):
                        position = int(Path(builtin_file_path).read_text(encoding="utf-8").strip())
                    position_map[extension_name] = position

                if (extension_name + ".py") not in file_names:
                    logging.warning(f"Missing {extension_name}.py file in {subdir_path}, Skip.")
                    continue

                # Dynamic loading {subdir_name}.py file and find the subclass of Extensible
                py_path = os.path.join(subdir_path, extension_name + ".py")
                spec = importlib.util.spec_from_file_location(extension_name, py_path)
                if not spec or not spec.loader:
                    raise Exception(f"Failed to load module {extension_name} from {py_path}")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                extension_class = None
                for name, obj in vars(mod).items():
                    if isinstance(obj, type) and issubclass(obj, cls) and obj != cls:
                        extension_class = obj
                        break

                if not extension_class:
                    logging.warning(f"Missing subclass of {cls.__name__} in {py_path}, Skip.")
                    continue

                json_data: dict[str, Any] = {}
                if not builtin:
                    if "schema.json" not in file_names:
                        logging.warning(f"Missing schema.json file in {subdir_path}, Skip.")
                        continue

                    json_path = os.path.join(subdir_path, "schema.json")
                    json_data = {}
                    if os.path.exists(json_path):
                        with open(json_path, encoding="utf-8") as f:
                            json_data = json.load(f)

                extensions.append(
                    ModuleExtension(
                        extension_class=extension_class,
                        name=extension_name,
                        label=json_data.get("label"),
                        form_schema=json_data.get("form_schema"),
                        builtin=builtin,
                        position=position,
                    )
                )

        sorted_extensions = sort_to_dict_by_position_map(
            position_map=position_map, data=extensions, name_func=lambda x: x.name
        )

        return sorted_extensions
