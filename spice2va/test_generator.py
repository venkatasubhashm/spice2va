import os
import unittest
import tempfile
import shutil

from src.generator import Generator
from src.llm.gemini import VerilogAModelOutput
from src.validator import ValidationReport

class TestGeneratorExtraction(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.generator = Generator(output_dir=self.test_dir)
        self.val_report = ValidationReport(
            structural="PASS", topology="PASS", parameters="PASS", physics="PASS", abstraction="PASS", overall="PASS", messages=[]
        )
        self.dummy_phys = {}

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_json_double_encoded_string(self):
        # The LLM outputs a stringified JSON string with literal \n and \" characters
        bad_code = '"`include \\"constants.vams\\"\\n`include \\"disciplines.vams\\"\\nmodule rc_lowpass(in, out);\\n    electrical in, out;\\n    analog begin\\n    end\\nendmodule"'
        
        model_output = VerilogAModelOutput(
            circuit_summary="Test", topology="Test", equations="Test", assumptions="Test",
            verilog_a_code=bad_code, validation_plan="Test", expected_behavior="Test"
        )
        
        va_path = self.generator.save("test_json", model_output, self.dummy_phys, self.val_report)
        
        with open(va_path, "r") as f:
            content = f.read()
            
        self._assert_valid_verilog_a(content)

    def test_markdown_wrapped_string(self):
        # The LLM outputs a markdown-wrapped code block
        md_code = '```verilog\n`include "constants.vams"\n`include "disciplines.vams"\nmodule rc_lowpass(in, out);\n    electrical in, out;\n    analog begin\n    end\nendmodule\n```'
        
        model_output = VerilogAModelOutput(
            circuit_summary="Test", topology="Test", equations="Test", assumptions="Test",
            verilog_a_code=md_code, validation_plan="Test", expected_behavior="Test"
        )
        
        va_path = self.generator.save("test_md", model_output, self.dummy_phys, self.val_report)
        
        with open(va_path, "r") as f:
            content = f.read()
            
        self._assert_valid_verilog_a(content)

    def _assert_valid_verilog_a(self, content: str):
        # 1. Contains module
        self.assertIn("module ", content)
        # 2. Contains analog
        self.assertIn("analog begin", content)
        # 3. Contains actual newline characters
        self.assertIn("\n", content)
        # 4. Does NOT contain literal \n sequences
        self.assertNotIn("\\n", content)
        # 5. Does NOT contain escaped quotes
        self.assertNotIn('\\"', content)
        # 6. Does NOT begin/end with Markdown fences
        self.assertNotIn("```", content)

if __name__ == "__main__":
    unittest.main()
