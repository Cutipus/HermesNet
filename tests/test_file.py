from hermesnet.protocol import File

def test_copy() -> None:
    f = File('Lorem', 'Ipsum', 400)
    g = f.copy()
    assert g == f

def test_repr() -> None:
    f = File('Lorem', 'Ipsum', 400)
    assert repr(f) == 'Lorem[Ipsum][400]'
