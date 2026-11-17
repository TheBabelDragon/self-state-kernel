//! SELF-State Kernel core — authoritative state semantics.
//!
//! `no_std` + optional `alloc`. No OS/hardware assumptions.
//! Does not implement BabelForge execution or ActionOS boot.

#![no_std]
#![forbid(unsafe_code)]

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::collections::BTreeMap;
#[cfg(feature = "alloc")]
use alloc::string::String;
#[cfg(feature = "alloc")]
use alloc::vec::Vec;

pub const SCHEMA_VERSION: &str = "self-state-kernel/0.1.1";

/// Leaf or traversal outcome for a path lookup.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Presence {
    /// Path component does not exist.
    Absent,
    /// Leaf path exists and is null.
    Null,
    /// Leaf path exists with a concrete value.
    Value,
    /// Intermediate value is a non-container (scalar); cannot descend.
    TypeConflict,
    /// Intermediate value is explicit null; cannot descend.
    NullTraversal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    Path,
    Value,
    TypeConflict,
    NullTraversal,
    NotFound,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StateError {
    pub code: ErrorCode,
    pub message: &'static str,
}

pub type StateResult<T> = Result<T, StateError>;

#[cfg(feature = "alloc")]
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    I64(i64),
    U64(u64),
    F64(f64),
    String(String),
    Bytes(Vec<u8>),
    Array(Vec<Value>),
    Map(BTreeMap<String, Value>),
}

#[cfg(feature = "alloc")]
impl Value {
    pub fn is_finite_number(&self) -> bool {
        match self {
            Value::F64(f) => f.is_finite(),
            Value::I64(_) | Value::U64(_) => true,
            _ => false,
        }
    }

    pub fn validate(&self) -> StateResult<()> {
        match self {
            Value::F64(f) if !f.is_finite() => Err(StateError {
                code: ErrorCode::Value,
                message: "non-finite float",
            }),
            Value::Array(items) => {
                for it in items {
                    it.validate()?;
                }
                Ok(())
            }
            Value::Map(m) => {
                for (k, v) in m {
                    if k.is_empty() || k.contains('.') {
                        return Err(StateError {
                            code: ErrorCode::Path,
                            message: "invalid map key",
                        });
                    }
                    v.validate()?;
                }
                Ok(())
            }
            _ => Ok(()),
        }
    }
}

#[cfg(feature = "alloc")]
fn split_path(path: &str) -> StateResult<Vec<&str>> {
    if path.is_empty() || path != path.trim() {
        return Err(StateError {
            code: ErrorCode::Path,
            message: "invalid path",
        });
    }
    let parts: Vec<&str> = path.split('.').collect();
    if parts.iter().any(|p| p.is_empty()) {
        return Err(StateError {
            code: ErrorCode::Path,
            message: "empty path segment",
        });
    }
    Ok(parts)
}

#[cfg(feature = "alloc")]
#[derive(Debug, Clone)]
pub struct Store {
    root: BTreeMap<String, Value>,
    version: u64,
}

#[cfg(feature = "alloc")]
impl Store {
    pub fn new() -> Self {
        Self {
            root: BTreeMap::new(),
            version: 0,
        }
    }

    pub fn version(&self) -> u64 {
        self.version
    }

    /// Lookup with full traversal classification.
    pub fn lookup(&self, path: &str) -> StateResult<(Presence, Option<&Value>)> {
        let parts = split_path(path)?;
        let mut current_map = &self.root;
        for (i, part) in parts.iter().enumerate() {
            let is_last = i + 1 == parts.len();
            match current_map.get(*part) {
                None => return Ok((Presence::Absent, None)),
                Some(Value::Null) if is_last => {
                    return Ok((Presence::Null, Some(&Value::Null)));
                }
                Some(Value::Null) => {
                    return Ok((Presence::NullTraversal, None));
                }
                Some(Value::Map(m)) if !is_last => {
                    current_map = m;
                }
                Some(v) if is_last => {
                    return Ok((Presence::Value, Some(v)));
                }
                Some(_) => {
                    return Ok((Presence::TypeConflict, None));
                }
            }
        }
        Ok((Presence::Absent, None))
    }

    pub fn get(&self, path: &str) -> Option<&Value> {
        match self.lookup(path) {
            Ok((Presence::Value, Some(v))) | Ok((Presence::Null, Some(v))) => Some(v),
            _ => None,
        }
    }

    pub fn set(&mut self, path: &str, value: Value) -> StateResult<()> {
        value.validate()?;
        let parts = split_path(path)?;
        let mut new_root = self.root.clone();
        let last = parts.len() - 1;
        let mut map = &mut new_root;
        for (i, part) in parts.iter().enumerate() {
            if i == last {
                map.insert((*part).into(), value);
                break;
            }
            match map.get(*part) {
                Some(Value::Map(_)) => {}
                Some(Value::Null) => {
                    return Err(StateError {
                        code: ErrorCode::NullTraversal,
                        message: "null intermediate",
                    });
                }
                Some(_) => {
                    return Err(StateError {
                        code: ErrorCode::TypeConflict,
                        message: "non-map intermediate",
                    });
                }
                None => {
                    map.insert((*part).into(), Value::Map(BTreeMap::new()));
                }
            }
            match map.get_mut(*part) {
                Some(Value::Map(m)) => map = m,
                _ => unreachable!(),
            }
        }
        self.root = new_root;
        self.version = self.version.saturating_add(1);
        Ok(())
    }
}

#[cfg(feature = "alloc")]
impl Default for Store {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_vs_null() {
        let mut s = Store::new();
        assert_eq!(s.lookup("a.b").unwrap().0, Presence::Absent);
        s.set("a.b", Value::Null).unwrap();
        assert_eq!(s.lookup("a.b").unwrap().0, Presence::Null);
        s.set("a.b", Value::I64(1)).unwrap();
        assert_eq!(s.lookup("a.b").unwrap().0, Presence::Value);
    }

    #[test]
    fn scalar_intermediate_lookup() {
        let mut s = Store::new();
        s.set("machine", Value::I64(42)).unwrap();
        assert_eq!(
            s.lookup("machine.temperature").unwrap().0,
            Presence::TypeConflict
        );
    }

    #[test]
    fn null_intermediate_lookup() {
        let mut s = Store::new();
        s.set("machine", Value::Null).unwrap();
        assert_eq!(
            s.lookup("machine.temperature").unwrap().0,
            Presence::NullTraversal
        );
    }

    #[test]
    fn path_conflict_write_atomic() {
        let mut s = Store::new();
        s.set("machine", Value::I64(42)).unwrap();
        let v = s.version();
        let err = s.set("machine.temperature", Value::I64(80)).unwrap_err();
        assert_eq!(err.code, ErrorCode::TypeConflict);
        assert_eq!(s.get("machine"), Some(&Value::I64(42)));
        assert_eq!(s.version(), v);
    }

    #[test]
    fn null_intermediate_write_atomic() {
        let mut s = Store::new();
        s.set("machine", Value::Null).unwrap();
        let v = s.version();
        let err = s.set("machine.temperature", Value::I64(80)).unwrap_err();
        assert_eq!(err.code, ErrorCode::NullTraversal);
        assert_eq!(s.lookup("machine").unwrap().0, Presence::Null);
        assert_eq!(s.version(), v);
    }

    #[test]
    fn nonfinite_rejected() {
        let mut s = Store::new();
        assert!(s.set("x", Value::F64(f64::NAN)).is_err());
        assert!(s.set("y", Value::F64(f64::INFINITY)).is_err());
        assert_eq!(s.version(), 0);
    }

    #[test]
    fn empty_path() {
        let mut s = Store::new();
        assert!(s.set("", Value::Bool(true)).is_err());
        assert!(s.set("a..b", Value::Bool(true)).is_err());
    }

    #[test]
    fn version_increments() {
        let mut s = Store::new();
        s.set("a", Value::I64(1)).unwrap();
        s.set("b", Value::I64(2)).unwrap();
        assert_eq!(s.version(), 2);
    }

    #[test]
    fn nested_valid() {
        let mut s = Store::new();
        s.set("a.b.c", Value::I64(7)).unwrap();
        assert_eq!(s.lookup("a.b.c").unwrap().0, Presence::Value);
        assert_eq!(s.get("a.b.c"), Some(&Value::I64(7)));
    }
}
