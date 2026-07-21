from brain.stage import GenerationStage
from schemas.presentation_design_schema import PresentationDesignOutput
from brain.presentation_expander import expand_presentation, reconcile_timing
from schemas.instruction_design_schema import InstructionDesign


class PresentationDesigner(GenerationStage[PresentationDesignOutput]):
    schema = PresentationDesignOutput
    prompt_filename = "presentation_designer.md"

    def run(self, input_data):
        output = expand_presentation(super().run(input_data))
        if isinstance(input_data, dict) and "instruction_design" in input_data:
            design = InstructionDesign.model_validate(input_data["instruction_design"])
            expected = {}
            for segment in design.segments:
                expected[segment.day] = expected.get(segment.day, 0) + segment.timing_minutes
            output = reconcile_timing(output, expected)
        return output
