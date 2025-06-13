from typing import Any

from jinja2 import Template


def render_config_secrets(
    config: dict[str, Any], secrets: dict[str, Any]
) -> dict[str, Any]:
    rendered_config = {}
    for key, value in config.items():
        template = Template(str(value))
        rendered_data = template.render(secrets)
        rendered_config[key] = eval(rendered_data)
    for key, value in rendered_config.items():
        config[key] = value
    return config
