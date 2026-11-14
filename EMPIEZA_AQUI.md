# Empieza aquí: el proyecto entero, explicado fácil

*(In English: [START_HERE.md](START_HERE.md))*

## El problema, en una historia

Hoy una IA ya puede escribir código. Le das un aviso de error y, diez
minutos después, tienes un arreglo que toca 237 archivos.

Antes de que ese arreglo entre en el producto, alguien tiene que
**revisarlo**. Y esa persona tiene dos opciones malas:

1. **Leerse los 237 archivos.** Son horas, y en el archivo 150 ya nadie
   presta atención de verdad.
2. **Darle a "aprobar" sin leer.** Es rápido, pero un día se cuela un fallo
   (o algo peor) y nadie sabe quién lo dejó pasar.

La idea obvia, "que lo revise otra IA", no lo arregla por sí sola, porque
las IA se inventan cosas. Mientras escribíamos *este mismo proyecto*, le
pedimos a una IA ejemplos de problemas en los cuatro cambios de código
reales, y **se inventó los cuatro**: archivos, funciones y códigos que no
existen, todo muy convincente.

La pregunta de verdad es: **¿cómo puede una persona fiarse de un cambio
escrito por una IA sin leerse cada línea y sin fiarse a ciegas de otra IA?**

## Nuestra respuesta, en una frase

> **La IA revisa, pero solo puede *señalar* líneas que existen. Un programa
> comprueba cada señal. La IA tiene que decir en voz alta qué decisiones no
> le tocan a ella. Y una persona firma un recibo con lo que comprobó y lo que
> no.**

*La IA revisa. Las personas firman. Las pruebas deciden.*

## Cómo funciona: la cocina de un restaurante

Imagina que un cambio de código es un plato que sale de la cocina.

| En la cocina | En nuestro proyecto |
|---|---|
| Un cocinero prepara el plato | Una IA escribe el cambio |
| Un inspector lo mira y apunta notas | La **IA revisora** busca problemas |
| Cada nota tiene que decir *"plato 3, arriba a la izquierda, este pelo"*; si no puede señalarlo, la nota se tira | El **juez** (código normal, sin IA) comprueba que cada queja señala una línea que existe de verdad en el cambio. Las quejas inventadas se tiran
| Hay cosas que no le tocan al inspector ("¿cambiamos la receta?"), y escribe *"no me toca a mí, pregunta al chef"* | La IA **se abstiene**: "esto cambia una promesa pública a los usuarios, que lo decida una persona" |
| ¿200 panecillos iguales? El inspector comprueba que siguen el patrón y prueba unos cuantos al azar | 220 archivos que recibieron el mismo cambio de 3 líneas se comprueban como patrón, y se enseña un puñado al azar a la persona |
| El jefe de cocina firma el ticket: *"he comprobado X, no he comprobado Y, acepto el riesgo"* | La persona escribe `/sign "Nombre"` y se genera un **recibo** |

## Qué encontró en el código real (nada inventado)

Lo probamos con 4 cambios reales escritos por una IA para MessagePack, una
librería de código abierto. El caso más llamativo:

**El cambio de 237 archivos (#2297).**
- En vez de 1.392 líneas, la persona lee **42**.
- 220 de los 222 archivos generados recibieron exactamente las mismas 3
  líneas. **Dos no.** La herramienta marcó esos dos, y llevaban a un cambio
  pequeño en otro sitio que nadie había pedido: la IA había colado una
  modificación que no tenía nada que ver.
- El cambio dice que una función "no está disponible" en versiones antiguas
  de .NET y la desactiva ahí. La documentación de Microsoft dice que *sí*
  está disponible. La herramienta no decide quién tiene razón: dice
  **"ABSTAINED: que decida una persona"** y enseña las dos cosas.
- Los tests **pasan** y aun así el requisito no se cumple, porque el test
  comprueba el comportamiento equivocado. Que los tests estén en verde no
  significa que el cambio esté bien.

**El cambio de la función nueva (#2129)** toca la API pública, así que la
herramienta dice "léetelo todo" (1.035 de 1.043 líneas). Cuando el riesgo
es alto no intenta ahorrar tiempo, y es a propósito.

## Funciona solo, en cada pull request

Todo esto es una **GitHub Action**. Nadie ejecuta nada a mano:

1. Una IA (o una persona) abre un pull request.
2. Al minuto aparece en el PR un comentario con el **brief**, y un check
   llamado `earned-trust/human-accountability-gate` sale **bloqueado**. La
   configuración del proyecto dice que, con ese check bloqueado, *no se
   puede hacer merge*.
3. El revisor contesta escribiendo comentarios en el PR, por ejemplo
   `/accept SCOPE-1` o `/sign "Tu Nombre"`. Cada comentario vuelve a lanzar
   la Action, que actualiza el brief y marca las casillas.
4. Cuando todo está contestado y un responsable ha firmado, el check se pone
   **en verde** con el **recibo** adjunto. Ahora sí se puede hacer merge.

La Action sabe quién escribió cada comentario porque se lo dice GitHub, así
que solo pueden firmar los dueños y colaboradores del repositorio. Si el PR
recibe un commit nuevo, la revisión empieza de cero: una firma vale
exactamente para el código que se revisó.

Ponerlo en un repositorio es copiar un archivo
([`templates/earned-trust.yml`](templates/earned-trust.yml)) en
`.github/workflows/`.

## Pruébalo tú (2 minutos)

Necesitas **Python 3**. No hay que instalar nada más, y funciona sin
internet.

Abre una terminal en esta carpeta y ejecuta:

```sh
# 1. Ejecutarlo todo: 4 revisiones, firmas de ejemplo, mediciones y dashboard (~15 s)
make demo

# 2. Mirar los resultados
open dashboard/index.html            # la página de mediciones
open runs/ju26-issue-2297/brief.md   # el informe que lee el revisor (se ve mejor en GitHub)
```

### Haz de revisor (los mismos comandos que escribirías en el PR)

Empieza una revisión nueva del cambio de 237 archivos:

```sh
python3 factory/et.py review --offline --branch ju26-issue-2297
```

Intenta firmar directamente. **No te deja**, y te dice qué falta:

```sh
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/sign "Tu Nombre"'
```

Haz lo que te pide:

```sh
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/spotcheck clean'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/decide ABS-1 remove-guard "La documentación de Microsoft dice que existe"'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept SCOPE-1'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept DRIFT-1'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept DRIFT-2'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept DRIFT-3'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/sign "Tu Nombre"'
```

Y abre tu recibo:

```sh
open runs/ju26-issue-2297/receipt.md
```

(`--as` es quién finges ser. En local solo pueden firmar los usuarios de
`factory/owners.json`; prueba con `--as otra-persona` y verás que te
rechaza. En GitHub, es GitHub quien le dice a la Action quién eres.)

## Qué significa cada comando

| Comando | En cristiano |
|---|---|
| `/spotcheck clean` | "He mirado la muestra al azar y está bien" (`escape` = "he encontrado algo mal": entonces tienes que leerlo todo) |
| `/decide ABS-1 <opción> "<por qué>"` | "La IA no quiso decidir esto; esta es mi decisión y mi motivo" |
| `/accept SCOPE-1` | "Sí, este problema es real y lo tengo presente" |
| `/refute SCOPE-1 "<por qué>"` | "No, esta queja está mal, y te digo por qué" |
| `/sign "Nombre Completo"` | "Me hago responsable de este cambio". Solo funciona cuando todo lo anterior está hecho |

## Palabras que vas a ver

- **Brief**: el informe corto que lee el revisor. Empieza con 5 líneas, y
  los detalles están plegados debajo.
- **Recibo** (*receipt*): el registro firmado de qué se comprobó, quién lo
  comprobó (máquina o persona), qué no se comprobó y qué riesgo se aceptó.
- **T0 / T1 / T2**: con cuánto cuidado tiene que leer una persona. T0 =
  resumen y una muestra al azar, T1 = solo las partes con riesgo, T2 = todo.
- **Juez**: código normal, sin IA. Tira cualquier queja que señale líneas
  que no existen.
- **Abstenerse**: la IA diciendo "esta decisión no me toca a mí".
- **VERIFIED / PARTIAL / UNVERIFIED / CONTRADICTED**: para cada cosa que el
  cambio dice de sí mismo, significan demostrado por un test que se ejecutó
  de verdad / hay test pero no se ejecutó / no hay pruebas / las pruebas
  dicen que es falso.
- **Defecto sembrado**: un fallo que metemos a propósito para medir si la
  herramienta lo pilla.

## Límites, con honestidad

- No teníamos clave de ninguna IA mientras lo construíamos, así que todos
  los problemas que enseña los encontraron reglas normales, no una IA. Con
  una clave, una IA añade más sospechas, y el juez las filtra igual.
- Las etiquetas de "¿esta queja es real?" (9 hallazgos) las puso la IA que
  ayudó a construir la herramienta. Debería revisarlas una persona.
- Las firmas de ejemplo de `runs/` son guiones y están marcadas como
  "simuladas". No enseñamos "minutos ahorrados" hasta que lo use gente real,
  porque no nos vamos a inventar ese número.
- El juez comprueba que una queja señala líneas reales, pero no puede
  comprobar si el *razonamiento* de la queja es correcto. Por eso una
  persona acepta o rechaza cada una.

## Para seguir

- El concepto en una página: [`docs/CONCEPT_CARD.md`](docs/CONCEPT_CARD.md)
- Cómo hacer la demo y el pitch: [`demo/PITCH_AND_DEMO_GUIDE.md`](demo/PITCH_AND_DEMO_GUIDE.md)
- Qué decidimos y por qué: [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md)
- Qué salió mal y qué aprendimos: [`docs/LESSONS_AND_FAILURE_MODES.md`](docs/LESSONS_AND_FAILURE_MODES.md)
- Cómo está organizado el código: [`factory/README.md`](factory/README.md)
