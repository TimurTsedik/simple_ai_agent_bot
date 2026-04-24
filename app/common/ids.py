import uuid


def generateId() -> str:
    ret = str(uuid.uuid4())
    return ret
