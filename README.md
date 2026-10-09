# Ashen Trial

Duelo 2D lateral em pixel art, com atmosfera gótica inspirada em *Blasphemous* e combate de chefe inspirado em *Dark Souls 3*. A luta é contra **Iudex Gundyr**, sem lock-on.

## Executar

```powershell
py -m pip install -r requirements.txt
py main.py
```

## Controles

| Ação | Controle |
|---|---|
| Mover | `A / D` |
| Pular | `W / seta para cima` |
| Ataque leve / combo | Botão esquerdo |
| Ataque forte | Botão direito |
| Esquivar | `Espaço / Shift` |
| Defender na direção do escudo | Segurar `F` |
| Aparar | `Q` |
| Usar frasco de cura | `E` |
| Mostrar ou ocultar ajuda | `H` |
| Mostrar ou ocultar hitboxes | `F3` |
| Pausar | `Esc` |
| Reiniciar após o fim | `R` |

O jogador tem vida, stamina, combo, ataque forte, cura, pulo, rolamento com invencibilidade, defesa direcional e aparo. Segurar `F` bloqueia golpes que chegam pela frente e consome stamina; ataques pelas costas ignoram o escudo. O chefe possui golpes com preparação e recuperação mais longas, recuos, investida, salto, combos, variações de tempo, golpes de área e uma segunda fase mais agressiva.

Durante o desenvolvimento, as hitboxes começam visíveis: azul para o jogador, laranja para o chefe, verde para ataques do jogador e vermelho para ataques do chefe.

## Animações

Idle, caminhada e defesa continuam vindo dos atlases 10×8 em `assets/animations_v3/`. As animações largas usam uma fonte independente por movimento em `assets/source_v5/`, organizada em uma grade invisível 5×2. O exportador transforma cada fonte em uma tira de dez células isoladas em `assets/animations_v5/`, com margem de segurança e linha de chão normalizada. Assim nenhuma espada ou alabarda invade o quadro vizinho.

- Cavaleiro: idle, corrida, rolamento, defesa, dois ataques leves e dois ataques fortes.
- Iudex Gundyr: idle, caminhada, duas varreduras, duas estocadas, golpe vertical e movimentos especiais.

Os atlases-fonte antigos ficam em `assets/hero_v3_atlas.png` e `assets/gundyr_v3_atlas.png`. Para reexportá-los, execute `py prepare_sprites.py`. Para reexportar as animações independentes corrigidas, execute `py prepare_independent_sprites.py`.
