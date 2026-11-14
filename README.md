# Bank demo

A tiny banking library, used to show how the Sancho review treats
critical code. `src/Bank/Payments/` is declared critical in
`.sancho.toml`: any change there is read in full and can only be signed
by its owner. Pull requests into this branch are reviewed by the Sancho
workflow; nothing here is a real bank.
