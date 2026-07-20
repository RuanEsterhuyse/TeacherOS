from brain.stage import GenerationStage
from schemas.analyzer_output_schema import CurriculumAnalyzerOutput


class CurriculumAnalyzer(GenerationStage[CurriculumAnalyzerOutput]):
    schema = CurriculumAnalyzerOutput
    prompt_filename = "curriculum_analyzer.md"
