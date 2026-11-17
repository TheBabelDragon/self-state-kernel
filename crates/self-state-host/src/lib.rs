//! Host harness with built-in parity cases (mirrors vectors/state_vectors.json).

use self_state_core::{ErrorCode, Presence, Store, Value};

pub fn run_builtin_vectors() -> Result<(), String> {
    {
        let store = Store::new();
        assert_presence(&store, "a.b", Presence::Absent)?;
    }
    {
        let mut store = Store::new();
        assert_presence(&store, "a.b", Presence::Absent)?;
        store
            .set("a.b", Value::Null)
            .map_err(|e| format!("set null: {e:?}"))?;
        assert_presence(&store, "a.b", Presence::Null)?;
        store
            .set("a.b", Value::I64(1))
            .map_err(|e| format!("set 1: {e:?}"))?;
        assert_presence(&store, "a.b", Presence::Value)?;
        if store.version() != 2 {
            return Err(format!("version want 2 got {}", store.version()));
        }
    }
    {
        let mut store = Store::new();
        store
            .set("machine", Value::I64(42))
            .map_err(|e| format!("{e:?}"))?;
        assert_presence(&store, "machine.temperature", Presence::TypeConflict)?;
        let v = store.version();
        let err = store
            .set("machine.temperature", Value::I64(80))
            .expect_err("scalar write");
        if err.code != ErrorCode::TypeConflict {
            return Err(format!("want TypeConflict got {:?}", err.code));
        }
        if store.version() != v {
            return Err("version changed on failed scalar write".into());
        }
        if store.get("machine") != Some(&Value::I64(42)) {
            return Err("machine mutated".into());
        }
    }
    {
        let mut store = Store::new();
        store
            .set("machine", Value::Null)
            .map_err(|e| format!("{e:?}"))?;
        assert_presence(&store, "machine.temperature", Presence::NullTraversal)?;
        let v = store.version();
        let err = store
            .set("machine.temperature", Value::I64(80))
            .expect_err("null write");
        if err.code != ErrorCode::NullTraversal {
            return Err(format!("want NullTraversal got {:?}", err.code));
        }
        if store.version() != v {
            return Err("version changed on failed null write".into());
        }
        assert_presence(&store, "machine", Presence::Null)?;
    }
    {
        let mut store = Store::new();
        store
            .set("a.b.c", Value::I64(7))
            .map_err(|e| format!("{e:?}"))?;
        assert_presence(&store, "a.b.c", Presence::Value)?;
        if store.version() != 1 {
            return Err(format!("nested version {}", store.version()));
        }
    }
    {
        let mut store = Store::new();
        if store.set("", Value::I64(1)).is_ok() {
            return Err("empty path should fail".into());
        }
        if store.version() != 0 {
            return Err("empty path must not bump version".into());
        }
    }
    Ok(())
}

fn assert_presence(store: &Store, path: &str, expect: Presence) -> Result<(), String> {
    let (p, _) = store.lookup(path).map_err(|e| format!("{e:?}"))?;
    if p != expect {
        return Err(format!("lookup {path}: got {p:?} want {expect:?}"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shared_vectors() {
        run_builtin_vectors().expect("vectors");
    }
}
