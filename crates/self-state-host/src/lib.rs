//! Host harness: execute shared vectors generated from vectors/state_vectors.json.

mod fixture;
mod generated_vectors;

use fixture::{Case, JsonValue, Op};
use generated_vectors::{CASES, CASE_COUNT, FORMAT};
use self_state_core::{ErrorCode, Presence, Store, Value};

pub fn fixture_format() -> &'static str {
    FORMAT
}

pub fn fixture_case_count() -> usize {
    CASE_COUNT
}

fn presence_from_str(s: &str) -> Result<Presence, String> {
    match s {
        "absent" => Ok(Presence::Absent),
        "null" => Ok(Presence::Null),
        "value" => Ok(Presence::Value),
        "type_conflict" => Ok(Presence::TypeConflict),
        "null_traversal" => Ok(Presence::NullTraversal),
        other => Err(format!("unknown presence {other}")),
    }
}

fn error_code_label(code: ErrorCode) -> &'static str {
    match code {
        ErrorCode::Path => "path",
        ErrorCode::Value => "value",
        ErrorCode::TypeConflict => "type_conflict",
        ErrorCode::NullTraversal => "null_traversal",
        ErrorCode::NotFound => "not_found",
    }
}

fn to_value(jv: &JsonValue) -> Result<Value, String> {
    match jv {
        JsonValue::Null => Ok(Value::Null),
        JsonValue::Bool(b) => Ok(Value::Bool(*b)),
        JsonValue::I64(i) => Ok(Value::I64(*i)),
        JsonValue::F64(f) => Ok(Value::F64(*f)),
        JsonValue::String(s) => Ok(Value::String((*s).into())),
        JsonValue::SpecialNan => Ok(Value::F64(f64::NAN)),
    }
}

fn values_equal(got: &Value, expect: &JsonValue) -> bool {
    match (got, expect) {
        (Value::Null, JsonValue::Null) => true,
        (Value::Bool(a), JsonValue::Bool(b)) => a == b,
        (Value::I64(a), JsonValue::I64(b)) => a == b,
        (Value::U64(a), JsonValue::I64(b)) if *b >= 0 => *a == *b as u64,
        (Value::F64(a), JsonValue::F64(b)) => a == b,
        (Value::String(a), JsonValue::String(b)) => a == *b,
        _ => false,
    }
}

fn run_case(case: &Case) -> Result<(), String> {
    let mut store = Store::new();
    for op in case.ops {
        match op {
            Op::Lookup { path, presence } => {
                let expect = presence_from_str(presence)?;
                let (got, _) = store
                    .lookup(path)
                    .map_err(|e| format!("{} lookup {path}: {e:?}", case.name))?;
                if got != expect {
                    return Err(format!(
                        "{} lookup {path}: got {got:?} want {expect:?}",
                        case.name
                    ));
                }
            }
            Op::Set {
                path,
                value,
                ok,
                error,
            } => {
                let before_v = store.version();
                let val = to_value(value)?;
                let res = store.set(path, val);
                match (res, *ok) {
                    (Ok(()), true) => {}
                    (Err(e), false) => {
                        if store.version() != before_v {
                            return Err(format!(
                                "{} set {path}: version changed on failure ({} -> {})",
                                case.name,
                                before_v,
                                store.version()
                            ));
                        }
                        if let Some(want) = error {
                            let got = error_code_label(e.code);
                            if got != *want {
                                return Err(format!(
                                    "{} set {path}: error {got} want {want}",
                                    case.name
                                ));
                            }
                        }
                    }
                    (Ok(()), false) => {
                        return Err(format!("{} set {path}: expected failure", case.name));
                    }
                    (Err(e), true) => {
                        return Err(format!("{} set {path}: unexpected err {e:?}", case.name));
                    }
                }
            }
            Op::Version { eq } => {
                if store.version() != *eq {
                    return Err(format!(
                        "{} version: got {} want {eq}",
                        case.name,
                        store.version()
                    ));
                }
            }
        }
    }
    if store.version() != case.final_version {
        return Err(format!(
            "{} final_version: got {} want {}",
            case.name,
            store.version(),
            case.final_version
        ));
    }
    for (path, expect) in case.final_paths {
        match store.lookup(path) {
            Ok((Presence::Value, Some(v))) | Ok((Presence::Null, Some(v))) => {
                if !values_equal(v, expect) {
                    return Err(format!(
                        "{} final_paths {path}: value mismatch got {v:?} want {expect:?}",
                        case.name
                    ));
                }
            }
            Ok((Presence::Null, None)) if matches!(expect, JsonValue::Null) => {}
            other => {
                return Err(format!(
                    "{} final_paths {path}: unexpected {other:?}",
                    case.name
                ));
            }
        }
    }
    Ok(())
}

/// Execute all shared fixture cases (generated from vectors/state_vectors.json).
pub fn run_shared_vectors() -> Result<(), String> {
    if CASE_COUNT == 0 {
        return Err("no shared vector cases".into());
    }
    for case in CASES {
        run_case(case)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shared_vectors_from_fixture() {
        run_shared_vectors().expect("shared vectors");
    }

    #[test]
    fn fixture_non_empty() {
        assert!(fixture_case_count() >= 8);
        assert!(fixture_format().contains("0.1.2"));
    }
}
