# Gundyr — caminhada redesenhada

Ferramenta: image_gen integrada, com transparência real. Fonte selecionada: exec-fc50b4c2-ccce-4d4f-8d97-5363907a8206.png, após criar poses novas e corrigir o layout. Fonte completa: `gundyr_walk.png` (1672×941), 16 desenhos completos. Não são poses montadas por rig ou quadros gerados por interpolação de pixels.

Referências: `../source_v5/boss_idle.png` define personagem, armadura e alabarda. O GIF e o diagrama de caminhada fornecidos pelo usuário orientam o movimento, não a identidade. O diagrama foi incluído na geração inicial das oito poses. As gerações seguintes criaram novos desenhos intermediários e corrigiram o espaçamento da fonte.

Exportação: `../../prepare_drawn_walk.py` extrai a silhueta de cada desenho completo, preserva sua borda alfa, aplica escala uniforme nos dois eixos e registra a pelve e a sola de apoio. A calibração por linha compensa as diferenças de escala do atlas gerado, sem separar ou deformar membros. PNGs finais: `../animations_v6/gundyr_walk/00.png` a `15.png`, células de 256×124 com margem transparente. O jogo carrega os arquivos individuais, sem recortar faixa compartilhada. Os antigos utilitários de rig/interpolação não fazem parte do fluxo atual.

## Geração das poses novas

```text
Create NEW full-body game sprite drawings, not copies of an idle pose. Use case: stylized-concept.
Image1 is ONLY Gundyr's design reference (not pose). Image2 is ONLY the walking pose diagram (not the character). Replace the stick figures in the walking diagram with the fully rendered SAME Gundyr character: crown-like closed visor helmet, muscular engraved grey plate armor, round knee guards, dark ragged skirt/cape, and one single consistent crescent halberd securely in both hands low in front. Same original painted game-sprite style and materials.
Output exactly EIGHT freshly drawn sequential walk poses in a 4-column by 2-row landscape 2:1 sprite sheet on REAL TRANSPARENCY. Wide EMPTY transparent gutters, every weapon tip and boot inside its cell, no labels/grid/ground/shadows. All sprites face RIGHT, same three-quarter side camera, same body proportions and pixel size. Torso and hips must actually change orientation across poses.
READ LEFT TO RIGHT TOP TO BOTTOM.
Top row:
1 Contact A: foreground bright plated leg stretched FORWARD toward RIGHT, rear darker leg stretched BACK toward LEFT, heel strike.
2 Down A: forward foreground leg bends to bear weight, rear heel lifts and knee folds behind.
3 Passing A: foreground support leg beneath hip, rear darker knee swings forward, rear boot OFF the ground beside the supporting shin.
4 Up A: rear darker leg EXTENDS FORWARD toward RIGHT and is about to land, foreground bright leg moves BACK toward LEFT with heel releasing.
Bottom row MUST reverse which leg leads, do NOT repeat the top row:
5 Contact B: foreground BRIGHT leg visibly stretched BACK to the LEFT (its bright round kneecap is LEFT of hip, boot also LEFT), the background DARK leg stretched FORWARD toward RIGHT (dark kneecap RIGHT of hip and boot RIGHT). This is opposite of pose1. Do NOT keep the bright leg forward. No mirroring of helmet or weapon.
6 Down B: background forward leg bends to bear weight, foreground heel lifts BEHIND LEFT.
7 Passing B: foreground BRIGHT knee swings forward with visibly lifted boot NEXT TO supporting dark shin, knees visibly flex. Foreground leg is not planted.
8 Up B: foreground BRIGHT leg EXTENDS FORWARD to RIGHT to land, darker support leg moves BACK LEFT, nearly returning to pose1.
Gundyr walks with real weight transfer as in the diagram, not a static lunge with only the back foot tapping. Both legs take turns as the support. Eight distinct full-body drawings, correct bent knees and boot lift, torso counterbalances the pelvis, slight rise/fall, natural armor articulation not rubbery deformation, cape follows. Complete uninterrupted halberd shaft and unchanged blade shape in every pose. Heavy walking not running. Preserve CHARACTER not the original static POSE. Each complete sprite at most70% its cell width and80% its cell height, wide transparent outer margins.
```

## Desenho dos quadros intermediários

```text
Use case: precise-object-edit. Create actual freshly drawn inbetween sprites, NOT geometric warp, cutout animation or crossfade.
Input1: the eight NEW Gundyr walk drawings, character identity AND movement key poses. Keep their same engraved grey armor, distinctive closed crown helmet, proportions, dark ragged skirt/cape, single complete ornate crescent halberd and two-handed grip. Eight key poses are read left-to-right top-to-bottom.
Make a production 16-frame walk sprite sheet by preserving those eight key drawings in poses1,3,5,7,9,11,13,15, and HAND-DRAWING complete new intermediate full-body poses2,4,6,8,10,12,14,16. Include the transition from last key to first. Draw actual bent knees, torso/shoulder weight transfer and cape motion, not repeated idle sprites.
MAIN CORRECTION: IN THE PASSING POSES (5,6,13,14) ONE BOOT IS CLEARLY LIFTED, as in input key3 and key7. Its entire sole is at least 10% of body height ABOVE the supporting sole. A 30-pixel minimum vertical gap at source scale, not only a heel lift. The passing knee bends and the hanging shin/boot advances under the hip. DO NOT align both boots to the ground. Only the SUPPORTING foot has to reach the ground baseline; the swing foot MUST LEAVE THE GROUND. One support foot throughout. In contact poses1 and9 both feet meet the floor. Forward reach poses7,8,15,16 extend the swing foot ahead toward right to complete actual steps. Near and far legs take turns. Whole torso genuinely responds, no static upper body.
LAYOUT correction: LANDSCAPE4:3 true-alpha PNG, exactly4 columns x4 rows equal cells,16 total, chronological row-major order. Same pixel size in all cells, all faceRIGHT, same fixed slightly-three-quarter side camera. Leave at least12% EMPTY transparent gutter on BOTH sides of every cell. Full helmet, cape, BOTH boots including airborne boots, and ENTIRE halberd blade/tip/shaft fit well within every cell, including outermost edges. Sprite occupies max70% cell width and75% cell height. Do not enlarge figures until weapons are clipped. Preserve weapon shape/size/side in all poses, no extra axe and no fragmented shaft. Keep regular origins but keep natural body rise/fall. NO text, numbers, grid lines, ground, shadows or checkers.
Return only the usable16-frame transparent sheet.
```

## Correção de layout e consistência

```text
Use case: precise-object-edit. Production cleanup of this16-frame hand-drawn Gundyr walk sheet.
Change ONLY production layout and consistent drawing scale; preserve ALL16 different full-body walk poses, their order, character identity, grey engraved armor, crowned visor helmet, ragged cape, lighting and ONE crescent halberd. Preserve bent knees and the genuinely LIFTED airborne boots. NEVER put the airborne boots down on the floor; maintain their vertical gap from the supporting boot. No new idle poses, no mirroring.
Recompose onto a MUCH WIDER LANDSCAPE16:9 canvas, ideally1920x1080. Exactly4 columns x4 rows. Each cell is wider than tall so the long halberd fits easily. Put a wide visible TRANSPARENT gutter of at least15% cell width on each side of EVERY complete sprite. Leave equally wide outer margins. Restore the complete curved blade tips on the last-column sprites, which are clipped in the input. Do not simply clip the tips again. The whole character and entire weapon must fit well inside a cell without touching the output image borders.
Make the anatomy/armor/helmet size CONSISTENT across ALL16 drawings: the last row is currently about8% smaller than row1; redraw/scale that row to the same body proportions and helmet/pauldron size as the other rows. Keep only SMALL natural torso down/up changes, maximum3% of body height, not changes in character size. Do not stretch legs or shrink boots. Keep existing walk mechanics and torso rotations.
IMPORTANT: Match the FOOT SUPPORT and KNEE poses of the INPUT EXACTLY, especially drawings3,5,6,7,11 with boots above the floor. One supporting sole can touch the imaginary ground; other foot must remain airborne when shown airborne. Do not align all soles to one line. No ground is drawn.
Actual alpha transparency, NO grid lines, labels, numbers, ground, shadows or backdrop. Preserve16 poses; correct only safe gutters, complete weapon tips and uniform character scale.
```
