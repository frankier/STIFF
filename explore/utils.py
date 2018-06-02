def parse_vars(vars):
    res = set()
    for var in vars.split(" "):
        var = var.split("<")[0]
        res.add(chr(int(var[2:], 16)))
    return res
