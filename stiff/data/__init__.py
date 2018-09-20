from os.path import dirname, join as pjoin


def get_data_path(path=None):
    data_path = dirname(__file__)
    if path is None:
        return data_path
    return pjoin(data_path, path)
