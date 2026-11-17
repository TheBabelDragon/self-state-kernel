fn main() {
    println!("self-state-host parity harness");
    match self_state_host::run_builtin_vectors() {
        Ok(()) => println!("vectors: ok"),
        Err(e) => {
            eprintln!("vectors: {e}");
            std::process::exit(1);
        }
    }
}
