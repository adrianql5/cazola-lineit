# Guía para el pitch y la demo

Esta guía está en español. **Lo que dices al jurado va en inglés, en
bloques de cita (>)**. Duración total: 5 minutos.

---

## 1. Qué tener listo la noche antes

**A. Los PRs en GitHub (la demo en vivo).** Una sola vez, desde la carpeta
del repo:

```sh
demo/setup_demo_fork.sh
```

El script crea un fork del repo del reto en tu cuenta, deja las 4 ramas de
la IA como 4 pull requests, y activa el workflow. Espera unos 3 minutos y
comprueba en `https://github.com/<tu-usuario>/junction26-messagepack-csharp/pulls`:

- [ ] cada PR tiene un comentario **"Earned-Trust Evidence Brief"**;
- [ ] cada PR tiene el check **`earned-trust/human-accountability-gate`** en
      amarillo o rojo (*action required*), y el botón de merge bloqueado.

Si algo falla, abre la pestaña **Actions** del fork y mira el log del run.

**B. El plan B, sin internet.** En el portátil:

```sh
make demo
```

Con eso tienes `runs/*/brief.md`, `runs/*/receipt.md` y `dashboard/index.html`
listos aunque no haya wifi.

**C. Las pestañas del navegador, en este orden:**

1. PR **#2297** del fork (el de 237 archivos), con el comentario del brief a la vista
2. Pestaña **Files changed** del mismo PR (para enseñar los 222 archivos plegados)
3. PR **#2129** (el de la API pública)
4. `dashboard/index.html`
5. `docs/CONCEPT_CARD.md` en GitHub (por si te preguntan)

**D. Un comentario preparado para pegar** en el PR #2297. Una sola caja con
todo, así la Action solo se ejecuta una vez:

```
/spotcheck clean
/decide ABS-1 remove-guard "Microsoft docs list the attribute for netstandard2.0 and .NET Framework 4.0+"
/accept SCOPE-1
/accept DRIFT-1
/accept DRIFT-2
/accept DRIFT-3
/sign "Adrian Quiroga"
```

> ⚠️ **No lo pegues antes de la demo**: firmarías el PR de verdad. Si ensayas
> con él, vuelve a dejar el PR limpio: borra tus comentarios y haz un commit
> vacío en la rama (`git commit --allow-empty -m "re-run" && git push demo ju26-issue-2297`).
> Un commit nuevo reinicia la revisión.

---

## 2. La idea en 3 frases (apréndetelas)

> **Problem:** AI writes code faster than people can review it. Reading all
> 237 files is impossible, and asking another AI to review it is no good
> either, because AIs make things up.
>
> **Solution:** the AI reviews, but it can only point at real lines, which a
> program checks. It says out loud which decisions it won't make. And a person
> signs a receipt saying what they checked and what they didn't.
>
> **Proof:** on the four real branches it cuts the 237-file PR to 42 lines to
> read, catches every bug we planted, and throws out every invented complaint.

Cierre: **"AI reviews. Humans sign. Evidence decides."**

---

## 3. Qué mira el jurado y dónde lo enseñas

| Criterio | Peso | Dónde lo ganas |
|---|---|---|
| **Clarity** | 30 % | Las 5 líneas del brief. La analogía del inspector de cocina. "42 de 1.392" |
| **Practicality** | 25 % | Es **un archivo** en `.github/workflows`. Se ejecuta solo en cada PR. Sin servidor. Bloquea el merge con las branch protections normales de GitHub |
| **Measurement** | 25 % | Dashboard: 14/14 defectos sembrados llegan a una persona; 36/36 citas falsas rechazadas; 208 → 0 escapes gracias a una mejora que salió de medir |
| **Evidence** | 20 % | Tests ejecutados de verdad en el PR; "Claims ↔ Evidence"; *What was NOT checked*; el recibo; ningún número inventado |

---

## 4. El guion, minuto a minuto

### 0:00 – 0:40 · El problema

*(En pantalla: el PR #2297, pestaña **Files changed**, haciendo scroll por
los 237 archivos.)*

> "It's Friday afternoon. An AI agent just opened this pull request: 237
> files, 1,392 changed lines. Somebody has to approve it. You can read all of
> it, which nobody really does, or click approve and hope.
>
> The obvious fix is 'let another AI review it'. We tried. Our own concept
> draft, written with an AI, came with four example bugs in these branches.
> All four were invented. Specific, convincing, and false."

### 0:40 – 1:20 · La solución en una imagen

*(Vuelve a la pestaña **Conversation**. Señala el check bloqueado y luego el
comentario del brief.)*

> "So we built the Earned-Trust PR Factory. It's a GitHub Action: one file in
> the repo. Nobody ran anything. The moment the PR was opened, it posted this
> brief, and this check, the human accountability gate, blocks the merge.
>
> Think of a food inspector in a kitchen. Every note must point at the exact
> plate: no pointing, no note. Some calls aren't the inspector's to make.
> And the head chef signs the ticket."

### 1:20 – 2:00 · Primero la historia: 42 líneas, no 1.392

*(Lee en voz alta las 5 líneas numeradas del brief.)*

> "Five lines. What it does, why, what else it touches, what I must read:
> **42 lines out of 1,392**. And one decision that's mine."

*(Abre el desplegable **Pattern**.)*

> "220 of the 222 generated files got exactly the same three lines. Two
> didn't. Both trace back to one line in `TransformUtilities.cs`: a formatting
> change nobody asked for, hidden inside a 237-file diff."

### 2:00 – 2:40 · Lo que la IA se negó a decidir

*(Abre **What the AI refused to decide**, y luego **Claims ↔ Evidence**.)*

> "The change turns the feature off for .NET Framework users, and says that's
> because the attribute doesn't exist there. Microsoft's documentation says it
> does. Now look: the tests **pass**. We ran them, in this PR. And the
> requirement is still *contradicted*, because the test checks the wrong
> behaviour. Should it stay? That's a compatibility promise. The AI says
> ABSTAINED, shows the evidence, and leaves the decision to a person."

### 2:40 – 3:10 · El juez contra las alucinaciones

*(Abre **Accusations the judge rejected**.)*

> "This accusation says `reader.Depth--` can underflow. It comes from our own
> draft. `reader.Depth--` appears nowhere in this diff, so the judge, which is
> plain code and not an AI, throws it out. No citation, no finding."

### 3:10 – 3:40 · El contraste: #2129

*(Pestaña del PR #2129.)*

> "Same factory, different PR: new public API, a new default wire format,
> four new build-breaking errors. Tier T2: read everything, 1,035 of 1,043
> lines, and four decisions for the maintainers. Here it saves no time, on
> purpose. Trust is earned, not assumed."

### 3:40 – 4:20 · Firmar en directo

*(Vuelve al PR #2297. Pega el comentario preparado y dale a **Comment**.
Mientras la Action trabaja, que tarda entre 20 y 40 segundos, sigue hablando.)*

> "I answer like any review: in a comment. I've looked at the random sample.
> I decide the compatibility question and give my reason. I accept the
> findings. And I sign with my name. If I'd tried to sign first, it would
> have refused, and someone without write access can't sign at all."

*(Recarga. El check se pone verde. Ábrelo: el recibo está en el output.)*

> "Green. And this is the receipt: what the machine checked, what I checked,
> what nobody checked and why, my decision, and the risk I accept. Pinned to
> this exact commit: push a new commit and the review starts over."

### 4:20 – 4:50 · Las mediciones

*(Pestaña del dashboard.)*

> "And we measured it. We planted 14 bugs in the real branches, and all 14
> reached a human. We corrupted 36 real citations, and the judge rejected all
> 36. A bug that keeps the shape of the pattern got through 208 times out of
> 221, so we fixed the classifier, and now it's zero. Every number says where
> it comes from. The review-minutes row is empty, because nobody real has used
> it yet, and we won't invent that number."

### 4:50 – 5:00 · Cierre

> "One file in your repo. Every AI-written PR gets a brief, a gate, and a
> named human who signs. **AI reviews. Humans sign. Evidence decides.**"

---

## 5. Si algo falla en directo

| Problema | Qué haces |
|---|---|
| No hay wifi o GitHub va lento | Plan B: abre `runs/ju26-issue-2297/brief.md` y `receipt.md` en local (el contenido es el mismo) y di *"this is the same brief, generated offline from the same diff"* |
| La Action tarda más de un minuto | Sigue con las mediciones (4:20) y vuelve al check al final |
| El check no se pone verde | Lee el comentario de respuesta en el brief (sección *Commands on this PR*): dice exactamente qué falta. Suele ser un ID mal copiado |
| Te equivocas y firmas antes de la demo | Commit vacío en la rama: la revisión se reinicia |

---

## 6. Preguntas probables del jurado (y respuestas cortas)

**"Without an LLM key, where does the AI come in?"**
> "The pipeline is built so that the AI is optional. Today every finding
> comes from deterministic rules, and the brief says 'LLM: NOT RUN'. With a key
> (any OpenAI-compatible endpoint, Vultr Serverless Inference for example),
> the AI adds accusations, and they go through the same judge. That's the
> point: the AI can't lower the bar."

**"Can't the AI still be wrong about a finding that cites a real line?"**
> "Yes. The judge checks the citation, not the argument. That's why every
> finding needs a human `/accept` or `/refute`, and the receipt records which
> it was."

**"How do you know 42 lines are enough?"**
> "We don't assume it, we measure it. Only files that match a pattern are
> hidden, the outliers always go to a human, a random sample seeded by the
> commit goes to a human, and planted bugs are how we test it. When a bug got
> through, we fixed the classifier."

**"What stops someone from just switching the workflow off?"**
> "Branch protection and the review of the workflow file itself. It's in our
> limits section. The gate is as strong as the repo's settings."

**"Why not a confidence score?"**
> "You can't argue with 87%. You can argue with 'this touches public API, so
> a person reads all of it'. Every decision is a rule a person can read."

**"Is the precision number real?"**
> "9 out of 9 findings are real, but the labels were made during the build,
> and the file says a person must re-check them. It's a small sample and we
> say so."

**"What does a developer have to install?"**
> "Nothing. One YAML file in `.github/workflows`, and optionally three secrets
> for the LLM."

---

## 7. Errores que debes evitar

- **No digas "the AI found"** cuando hables de los hallazgos de hoy: los
  encontraron reglas deterministas. Di *"the factory found"*.
- **No digas que ahorra X minutos.** No lo hemos medido con personas reales.
- **No enseñes los recibos de `runs/` como si fueran de usuarios reales**:
  son sesiones guionizadas y lo pone en cada evento (`simulated`).
- **No digas que los tests de #2234 y #2129 pasaron con el SDK fijado**:
  pasaron con el SDK 9, y el brief lo dice (*deviation*). Si te preguntan,
  explícalo: es un problema del entorno (CS9057), no del cambio.
- **Habla de lo que la IA no hace** (abstenerse, no inventar) tanto como de
  lo que hace. Es lo que diferencia el proyecto.
