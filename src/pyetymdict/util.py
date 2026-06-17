__all__ = ['split']

def split(s, sep=';'):
    return [ss.strip() for ss in (s or '').split(sep) if ss.strip()]
