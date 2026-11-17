//! Fixture types shared by generated vectors and the runner.

#![allow(dead_code)]

#[derive(Debug, Clone)]
pub enum JsonValue {
    Null,
    Bool(bool),
    I64(i64),
    F64(f64),
    String(&'static str),
    SpecialNan,
}

#[derive(Debug, Clone)]
pub enum Op {
    Lookup {
        path: &'static str,
        presence: &'static str,
    },
    Set {
        path: &'static str,
        value: JsonValue,
        ok: bool,
        error: Option<&'static str>,
    },
    Version {
        eq: u64,
    },
}

#[derive(Debug, Clone)]
pub struct Case {
    pub name: &'static str,
    pub ops: &'static [Op],
    pub final_version: u64,
    pub final_paths: &'static [(&'static str, JsonValue)],
}
