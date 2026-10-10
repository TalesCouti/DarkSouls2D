# Gundyr — acabamento da caminhada sem delineado extra

Fonte selecionada: `gundyr_walk_painted.png` (**1670×942**, RGBA), gerada com **image_gen integrada**; saída `exec-59df677d-d6c4-4fd2-9ec1-a843eb469aba.png`. Não foi usado CLI nem filtro de contorno/cor em execução. A versão anterior `gundyr_walk_consistent.png` e os sprites de idle/ataque foram preservados.

O alvo foi somente a caminhada: reduzir o traço preto uniforme nas bordas e entre placas, substituindo-o por bordas pintadas, textura e sombras de material mais próximas do idle e dos ataques. Referências: `../source_v5/boss_idle.png` e `../source_v5/boss_sweep_a.png`. Um segundo passe conteve o brilho que a primeira edição introduziu, usando a versão anterior apenas como referência de valores de cor, sem restaurar seu contorno.

Mantidos os 16 desenhos completos, a sequência das passadas, botas suspensas, inclinação/contrapeso do torso, direção da alabarda e cadência-base de 1,6 s. O exportador `../../prepare_drawn_walk.py` continua extraindo cada silhueta completa e aplicando apenas escala uniforme por linha e registro de pelve/chão: não recorta/move membros nem gera quadros por interpolação. A altura de referência continua em 86 px; os pontos de registro e a dimensão real da fonte foram recalibrados para a nova edição. Células finais de 256×124, apoio da sola em y=122.

PNGs em uso: `../animations_v6/gundyr_walk/00.png` a `15.png`. O jogo, os golpes, hitboxes, idle e velocidade de deslocamento não foram modificados. Os testes de arte comparam a paleta com idle/varreduras e detectam bordas muito escuras ao lado de material iluminado: a versão anterior tinha aproximadamente 19% dessas bordas com aspecto de traço preto, contra menos de 1% na versão repintada. Essa verificação não elimina tecido escuro nem sombras naturais; a comparação visual foi feita no tamanho de jogo e com ampliação.

## Edição do acabamento

```text
Use case: style-transfer (precise existing-sprite edit).
Asset type: production sixteen-frame Gundyr walk atlas, real transparent PNG.
Image1 is the EDIT TARGET: the sixteen approved chronological walking poses (four columns x four rows).
Image2 is the STYLE REFERENCE: the game's existing Gundyr idle sprites.
Image3 is the STYLE REFERENCE: the game's existing Gundyr attack sprites.
Edit ONLY Image1. Do NOT change or output Image2/Image3, and do not copy their poses.

The walking sprites currently have a thick dark BLACK INK OUTLINE around the entire silhouette and strong black comic-style delineation between every armor plate. The idle and attacks do NOT have that graphic outline; they are weathered, softly painted/textured dark-grey iron. Remove this extra inked/outlined look from ALL16 WALK FRAMES so there is no art-style switch when the boss starts walking.

Repaint the walk's external black stroke and heavy internal ink lines as naturally shaded adjoining material: softer painterly edges, subtle contact shadows only, consistent grey plate texture/engraving and distressed grain as in the reference idle/attack. KEEP armor seams and real shadow recesses, but eliminate the uniform thick black line traced around shoulders, helmet, chest, boots, cape hems and halberd blade. No black sticker border, no outline ring, no light/white halo. Surface treatment must match Image2/Image3's restrained textured hand-painted iron, not smooth glossy comic armor. Natural material shading and fine texture, no harsh graphic contour. Keep muted grey iron color and restrained highlights matching the references; do not brighten or tint bronze.

ABSOLUTE invariants: preserve all SIXTEEN unique walking drawings' exact silhouettes, body size/proportions, pose sequence, leaned/counterbalancing torso, knee bends, lifted swing feet and support soles, single complete crescent halberd, two-handed grip, facing RIGHT and same three-quarter side camera. Do not replace with idle poses, alter motion, add a weapon or shorten boots/blade. Keep the exact source layout and locations,1671x941 wide landscape,4columns x4rows, with the current BIG empty transparent horizontal/vertical gutters. All poses stay separate; every complete tip and sole inside its cell. Do NOT enlarge or shrink characters or move limbs. Only repaint the line/edge style and weathered texture to match the existing idle and attack artwork. Actual alpha transparency, no ground/shadows/text/grid/labels/checker/backdrop. Return ONLY the usable corrected sixteen-frame walk sheet.
```

## Contenção de brilho sem restaurar o contorno

```text
Use case: style-transfer. Final COLOR/FINISH ONLY pass.
Image1 is the EDIT TARGET: sixteen walking sprites with the improved soft painted edges.
Image2 is a COLOR VALUES ONLY reference: the previous walk's darker metal palette. Do NOT copy its black ink contour back into Image1.
Image3 is the game's IDLE STYLE reference: subdued grainy weathered grey iron, painted shading without a traced ink outline.

Keep the newly softened painterly edges of Image1, but its metal is now too bright. Lower its lit grey metal values and highlights by about25% to match Image2 and Image3. Weathered dull medium-dark iron, not shiny pale silver. Midtone lit plate should be near RGB(90,86,84), strongest raised grey highlights near RGB(140,136,134), shaded iron near(45,43,42). Keep the dark cape/shadows unchanged. Add the fine distressed/grainy painted texture of Image3, not smooth plastic cel-shading. A quiet textured grey color on the shoulder/chest/boots/knees/halberd, NOT white edge stripes.

IMPORTANT: DO NOT restore a uniform dark BLACK stroke around the silhouette or between armor plates. The current softened edge treatment must remain. Armor seams should be subtle painted material shadows, not heavy line art. No bright rim light, no white/black sticker halo, no traced cartoon outline. Corrected brightness and the idle's weathered texture ONLY.

Preserve Image1's EXACT16 approved walk poses and chronological order, leaning torso, knee bends, lifted swing feet, sole locations, complete single crescent halberd, two-handed grip, RIGHT facing and anatomy size/proportions. Keep EXACT current wide landscape atlas1670x942,4columns x4rows, drawing locations and LARGE transparent gutters. Do not move limbs, resize drawings, fill gutters, replace poses with idle or change animation. Actual transparent alpha. No floor/shadow/text/labels/grid/background/checkers. Return ONLY the final usable sixteen-frame walk atlas, same geometry and soft edges with subdued textured grey iron matching idle.
```
