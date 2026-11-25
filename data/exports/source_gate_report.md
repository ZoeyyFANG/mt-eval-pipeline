# Source gate: v1 vs v2

164 strings with human QE labels (73 error labels over all engine outputs).

| | v1 (one LLM call decides all) | v2 (rules + narrow LLM) |
|---|---|---|
| Strings held before MT | 80 | 15 |
| Share held % | 48.8 | 9.1 |
| Error rate, held strings % | 29.7 | 28.0 |
| Error rate, passed strings % | 16.0 | 22.4 |
| Share of all errors in held strings % | 64.4 | 9.6 |
| Lift (held error rate / overall) | 1.3 | 1.2 |
| Share of meaning errors in held strings % (errors the post-MT rules can't catch) | 80.0 | 8.0 |

- 29 strings v1 held only for a placeholder are passed by v2: the token check after MT already blocks a broken placeholder.
- Count-dependent strings are recorded, not held: zh-CN has one plural form (CLDR), so no ICU plural variants are needed. For ru / pl / ar they would be held.

## Questions v2 would send to the developer

- `commandPalette.shortcuts.close` "Close": In the command palette shortcuts list, does 'Close' refer to the action of closing the command palette (or a dialog), and is it a verb label rather than an adjective like 'near'?
- `helpDialog.deepBoxSelect` "Deep select within box, and prevent dragging": In this shortcut hint, what does 'deep select' mean: selecting elements inside groups/frames within the selection box, or selecting elements hidden underneath other elements? And does 'prevent dragging' refer to stopping the selected element from being moved when you click-drag inside the box?
- `helpDialog.github` "Found an issue? Submit": Is 'Found an issue? Submit' a sentence fragment that is followed by separate linked text (e.g. 'on GitHub' or 'a report'), and if so what exactly follows it, so the Chinese verb and word order can be arranged correctly?
- `hints.arrowTool` "Click to start multiple points, drag for single line. Press {{shortcut}} again to change arrow type.": In 'Click to start multiple points, drag for single line', does clicking begin a multi-point (multi-segment) arrow where each subsequent click adds a vertex, and does 'arrow type' mean the arrow routing style (sharp/curved/elbow) rather than the arrowhead style?
- `hints.linearElement` "Click to start multiple points, drag for single line": In 'Click to start multiple points', does 'start' mean beginning a multi-point line (polyline) whose points are added by further clicks, or does 'multiple points' refer to something else (e.g., selecting/editing several points)? Also, what does 'single line' contrast with: a straight two-point line?
- `imageExportDialog.label.embedScene` "Embed scene": Does 'Embed scene' mean saving the Excalidraw scene data inside the exported image file (so the image can be re-imported and edited), or generating embed code to place the scene in an external webpage?
- `labels.arrowhead_cardinality_many` "Cardinality (many)": Is this arrowhead option the entity-relationship (ER) diagram crow's-foot notation marking the 'many' side of a relationship, so that 'Cardinality' should be translated using the database/ER term (e.g. 基数/多重性) rather than a generic mathematical meaning?
- `labels.large` "Large": The key 'labels.large' is generic: does 'Large' refer to a size option for stroke width, font size, or something else, and is it paired with Small/Medium/Extra large options in the same context?
- `labels.sharp` "Sharp": Where does 'Sharp' appear in the UI: is it the shape edge/corner style option (opposite of 'Round'), the arrow/line path type, or something else like image sharpness?
- `labels.small` "Small": Where is the 'Small' label used: for stroke width, font size, or another size setting (e.g. arrowhead size, roundness)? The key 'labels.small' is generic and doesn't indicate which property is being sized.
- `library.hint_emptyLibrary` "Select an item on canvas to add it here, or install a library from the public repository, below.": In the UI, does 'below' point to where the public repository link or button is displayed under this hint text, and should the Chinese read as 'see the link below' (e.g., 在下方的公共库中安装) rather than as a modifier of the whole sentence?
- `toolBar.convertElementType` "Toggle shape type": What does 'shape type' refer to here: converting a selected element between basic shapes (rectangle/diamond/ellipse), or switching a line/arrow between types (e.g., straight/curved/elbow)? And is this a tooltip/label for a button that performs the switch?
