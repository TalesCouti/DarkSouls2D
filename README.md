# Ashen Trial

Duelo 2D lateral em pixel art, com atmosfera gótica inspirada em *Blasphemous* e combate de chefe inspirado em *Dark Souls 3*. A luta é contra **Iudex Gundyr**, sem lock-on.

A arena usa um pátio gótico em ruínas, com muralhas, túmulos, névoa e iluminação fria. Ao morrer, uma transição escura exibe “VOCÊ MORREU” antes da opção de renascer.

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
| Beber Estus | `E` |
| Mostrar ou ocultar ajuda | `H` |
| Mostrar ou ocultar hitboxes | `F3` |
| Pausar | `Esc` |
| Reiniciar após o fim | `R` |

O jogador tem vida, stamina, combo, ataque forte, cura, pulo, rolamento com invencibilidade, defesa direcional e aparo. Ao pressionar `E`, ele saca e bebe o Estus; comandos do jogador não cancelam a animação, mas um ataque inimigo pode interrompê-la. A cura só é aplicada no momento do gole. Segurar `F` bloqueia golpes que chegam pela frente e consome stamina; ataques pelas costas ignoram o escudo. O chefe possui golpes com preparação e recuperação mais longas, recuos, investida, salto, combos, variações de tempo, golpes de área e uma segunda fase mais agressiva.

Durante o desenvolvimento, as hitboxes começam visíveis: azul para o jogador, laranja para o chefe, verde para ataques do jogador e vermelho para ataques do chefe.

## Animações

Todas as animações do cavaleiro e os movimentos largos do chefe usam uma fonte independente por movimento em `assets/source_v5/`, organizada em uma grade invisível 5×2. O exportador transforma cada fonte em uma tira de dez células isoladas em `assets/animations_v5/`, com margem de segurança, botas completas e linha de chão normalizada. Assim nenhuma espada, alabarda ou parte dos pés invade o quadro vizinho.

- Cavaleiro: idle, corrida, rolamento, defesa, beber Estus, morte com pose final deitada, dois ataques leves e dois ataques fortes.
- Iudex Gundyr: identidade alta e assimétrica inspirada na referência, alabarda consistente, idle, caminhada, duas varreduras, duas estocadas, golpe vertical e movimentos especiais.

Os atlases-fonte antigos ficam em `assets/hero_v3_atlas.png` e `assets/gundyr_v3_atlas.png`. Para reexportá-los, execute `py prepare_sprites.py`. Para reexportar as animações independentes corrigidas, execute `py prepare_independent_sprites.py`.
