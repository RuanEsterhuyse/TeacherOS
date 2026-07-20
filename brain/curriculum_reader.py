from brain.stage import GenerationStage
from schemas.reader_output_schema import CurriculumReaderOutput


class CurriculumReader(GenerationStage[CurriculumReaderOutput]):
    schema = CurriculumReaderOutput
    prompt_filename = "curriculum_reader.md"
