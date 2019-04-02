from copy import copy


def conf_net_search(auto, conf_net, elem_id_fn=lambda x: x):
    """
    Searches a confusion network (encoded as an iterable of iterables) with an
    Aho-Corasick Automaton (ACA). It does this by keeping several pointers into
    the ACA. Pointer uniqueness is maintained.

    Theoretically, we can remove dominated nodes, which are redundant, Given
    some pointer which has a some route r_1 from the start node, it is
    dominated by a pointer with route r_2 from the start node if r_1 is a
    suffix of r_2 and r_2 is longer than r_1. So if we have pointers and routes
    like so:

    start->a->b->c->pointer 1
    start->b->c->pointer 2
    start->c->pointer 3

    Then pointers 2 and 3 are dominated by pointer 1 and pointer 3 is dominated
    by pointer 2. This means that all pointers apart from pointer 1 are
    redundant.

    Currently, this isn't fully utilised. Instead, the root is removed if there
    are any other pointers, which is the trivial example of this case.
    """
    root = auto.iter(())
    root_id = root.pos_id()
    auto_its = [root]

    for opts in conf_net:
        # Don't add the root pointer to begin with
        seen_auto_its = {root_id}
        next_auto_its = []
        # We can get duplicates with the current scheme, so filter
        elem_ids = set()
        elems = []
        # Save the current root to ensure the right character index
        cur_root = None
        for auto_it in auto_its:
            for opt in opts:
                new_auto_it = copy(auto_it)
                new_auto_it.set((opt,))
                for elem in new_auto_it:
                    if new_auto_it.pos_id() in next_auto_its:
                        break
                    elem_id = elem_id_fn(elem)
                    if elem_id not in elem_ids:
                        elem_ids.add(elem_id)
                        elems.append(elem)
                if new_auto_it.pos_id() not in seen_auto_its:
                    seen_auto_its.add(new_auto_it.pos_id())
                    next_auto_its.append(new_auto_it)
                elif new_auto_it.pos_id() == root_id:
                    cur_root = new_auto_it
        for elem in elems:
            yield elem
        # If we end up with nothing, add back the root
        if len(next_auto_its) == 0:
            next_auto_its.append(cur_root)
        auto_its = next_auto_its


def conf_net_search_simple(auto, conf_net, elem_id_fn=lambda x: x):
    """
    As above, but take no account of domination
    """
    root = auto.iter(())
    auto_its = [root]

    for opts in conf_net:
        # Don't add the root pointer to begin with
        next_auto_its = []
        # We can get duplicates with the current scheme, so filter
        elem_ids = set()
        elems = []
        for auto_it in auto_its:
            for opt in opts:
                new_auto_it = copy(auto_it)
                new_auto_it.set((opt,))
                for elem in new_auto_it:
                    if new_auto_it.pos_id() in next_auto_its:
                        break
                    elem_id = elem_id_fn(elem)
                    if elem_id not in elem_ids:
                        elem_ids.add(elem_id)
                        elems.append(elem)
                next_auto_its.append(new_auto_it)
        for elem in elems:
            yield elem
        auto_its = next_auto_its
