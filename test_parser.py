from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel


class ExtractOutput(BaseModel):
    bill_extracts: str


parser = PydanticOutputParser(pydantic_object=ExtractOutput)
format_instructions = parser.get_format_instructions()
print(format_instructions)
