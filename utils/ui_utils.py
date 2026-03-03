def get_all_children(widget):
    children = []
    for child in widget.children():
        children.append(child)
        children.extend(get_all_children(child))
    return children
