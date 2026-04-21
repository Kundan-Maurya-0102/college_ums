from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get dict item by variable key: {{ my_dict|get_item:key }}"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def marks_display(marks_dict, exam_type):
    """Get marks info for a specific exam type: returns 'obtained/max' string."""
    if isinstance(marks_dict, dict) and exam_type in marks_dict:
        m = marks_dict[exam_type]
        return f"{m['obtained']}/{m['max']}"
    return "—"


@register.filter
def marks_pct(marks_dict, exam_type):
    """Get percentage for exam_type from marks dict."""
    if isinstance(marks_dict, dict) and exam_type in marks_dict:
        return marks_dict[exam_type].get('pct', 0)
    return None
