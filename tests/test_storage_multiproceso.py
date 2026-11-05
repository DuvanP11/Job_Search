import multiprocessing as mp

from autoapply.storage import Store


def _incrementar(ruta, n):
    st = Store(data_dir=ruta, database_url='')
    for _ in range(n):
        st.mutate('c', 'u', 'contador', lambda r: {**r, 'valor': r['valor'] + 1})


def test_mutate_no_pierde_actualizaciones_entre_procesos(tmp_path):
    st = Store(data_dir=str(tmp_path), database_url='')
    st.save('c', 'u', {'id': 'contador', 'valor': 0}, )
    procs = [mp.get_context('fork').Process(target=_incrementar, args=(str(tmp_path), 25)) for _ in range(4)]
    [p.start() for p in procs]
    [p.join(60) for p in procs]
    assert st.get('c', 'u', 'contador')['valor'] == 100


def test_candado_reentrante_no_se_bloquea(tmp_path):
    st = Store(data_dir=str(tmp_path), database_url='')
    st.save('c', 'u', {'id': 'a', 'v': 1})
    # Guardar dentro de mutate (otra colección) no debe bloquearse. Ojo: guardar en LA MISMA
    # colección dentro de mutate se pierde, porque mutate escribe su copia previa.
    st.mutate('c', 'u', 'a', lambda r: (st.save('otra', 'u', {'id': 'b', 'v': 2}), {**r, 'v': 9})[1])
    assert st.get('c', 'u', 'a')['v'] == 9 and st.get('otra', 'u', 'b')['v'] == 2


def test_owners(tmp_path):
    st = Store(data_dir=str(tmp_path), database_url='')
    st.save('cola', 'u1', {'id': 'x'})
    st.save('cola', 'u2', {'id': 'y'})
    st.save('otra', 'u3', {'id': 'z'})
    assert sorted(st.owners('cola')) == ['u1', 'u2']
