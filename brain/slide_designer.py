from brain.stage import GenerationStage
from schemas.slide_specification_schema import SlideSpecification


class SlideDesigner(GenerationStage[SlideSpecification]):
    schema = SlideSpecification
    prompt_filename = "slide_designer.md"
