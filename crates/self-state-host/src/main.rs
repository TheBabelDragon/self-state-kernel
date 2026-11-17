fn main() {
    println!(
        "self-state-host format={} cases={}",
        self_state_host::fixture_format(),
        self_state_host::fixture_case_count()
    );
    match self_state_host::run_shared_vectors() {
        Ok(()) => println!("vectors: ok"),
        Err(e) => {
            eprintln!("vectors: {e}");
            std::process::exit(1);
        }
    }
}
