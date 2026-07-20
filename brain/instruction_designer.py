from brain.stage import GenerationStage
from schemas.instruction_design_schema import InstructionDesign


class InstructionDesigner(GenerationStage[InstructionDesign]):
    schema = InstructionDesign
    prompt_filename = "instruction_designer.md"
