from fastapi import Path

##########################################################################################################
RESOURCE_ID_PREFIX_REGEX = r"^(MTBLS|REQ)[1-9][0-9]{0,20}$"
TABLE_COLUMN_INDEX_REGEX = r"^[0-9]{1,10}$"

RESOURCE_ID_DESCRIPTION = "MetaboLights study submission id or accession number"
RESOURCE_ID_IN_PATH = Path(
    pattern=RESOURCE_ID_PREFIX_REGEX, description=RESOURCE_ID_DESCRIPTION
)
TABLE_COLUMN_INDEX_IN_PATH = Path(
    pattern=TABLE_COLUMN_INDEX_REGEX,
    description="ISA table column index starts from 0.",
)
TASK_ID_IN_PATH = Path(description="Started task id")
