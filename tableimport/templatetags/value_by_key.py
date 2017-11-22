from django.template.defaulttags import register


@register.filter
def keyvalue(dict, key):
    return dict.get(key,'')

@register.filter
def fieldvalue(obj, key):
    try:
        f = getattr(obj, key)
    except:
        f = ""
    return f