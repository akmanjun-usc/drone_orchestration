"""
Code extractor.

Pulls the Python code block out of an LLM response string.
Handles the common variants the model might produce.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Matches ```python ... ``` or ``` ... ```
_FENCED_PATTERN = re.compile(
    r"```(?:python)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_code(response_text: str) -> str:
    """
    Extract Python source from a fenced code block in the LLM response.

    Args:
        response_text: Raw text returned by the LLM.

    Returns:
        The extracted Python code as a string.

    Raises:
        ValueError: If no code block is found in the response.
    """
    matches = _FENCED_PATTERN.findall(response_text)

    if not matches:
        # Last resort: maybe the model returned raw code with no fences
        stripped = response_text.strip()
        if stripped.startswith(("def ", "import ", "from ", "#", "state", "fly_", "take")):
            logger.warning("No fenced code block found; treating entire response as code.")
            return stripped
        raise ValueError(
            "No Python code block found in LLM response.\n"
            f"Response was:\n{response_text[:500]}"
        )

    if len(matches) > 1:
        logger.warning("Multiple code blocks found; using the first one.")

    return matches[0].strip()
