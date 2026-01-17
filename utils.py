import bidi.algorithm

def fix_hebrew_text(text):
    """
    Reverses Hebrew text for proper display in matplotlib charts.
    """
    if not isinstance(text, str):
        return text
    return bidi.algorithm.get_display(text)