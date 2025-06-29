import pytest
import tempfile
import os
import glob
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor


class TestNotebookExecution:

    def get_notebook_paths(self):
        examples_dir = os.path.join(
            os.path.dirname(__file__), "..", "examples")
        examples_dir = os.path.abspath(examples_dir)
        notebook_paths = glob.glob(os.path.join(examples_dir, "*.ipynb"))
        return notebook_paths

    @pytest.mark.slow
    def test_all_notebooks_batch(self):
        # Test all notebook in the ../examples directory
        notebook_paths = self.get_notebook_paths()
        failed_notebooks = []

        for notebook_path in notebook_paths:
            notebook_name = os.path.basename(notebook_path)

            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Read and execute notebook
                    with open(notebook_path, 'r', encoding='utf-8') as f:
                        nb = nbformat.read(f, as_version=4)

                    ep = ExecutePreprocessor(
                        timeout=300,
                        kernel_name='python3',
                        allow_errors=False
                    )

                    ep.preprocess(nb, {'metadata': {'path': tmpdir}})

            except Exception as e:
                failed_notebooks.append((notebook_name, str(e)))

        if failed_notebooks:
            error_msg = "The following notebooks failed to execute:\n"
            for name, error in failed_notebooks:
                error_msg += f"  - {name}: {error}\n"
            pytest.fail(error_msg)
