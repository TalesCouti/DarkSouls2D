# Ashen Trial

Jogo 2D lateral em pixel art inspirado em *Dark Souls 3*, com exploração pelo **Cemitério das Cinzas**, combate metódico e uma luta contra **Iudex Gundyr**, sem lock-on.

O percurso começa junto a uma fogueira, atravessa ruínas, túmulos, névoa e grupos de Hollows e termina no portão de névoa da arena. O portão usa camadas procedurais e partículas animadas e, ao interagir, conduz o jogador pela fumaça antes de iniciar Gundyr. A fogueira restaura vida, stamina e Estus e faz os inimigos renascerem. Ao morrer, uma transição escura exibe “VOCÊ MORREU” antes da opção de renascer na fogueira.

## Executar

```powershell
py -m pip install -r requirements.txt
py main.py
```

Ao abrir, o jogo apresenta o menu principal. Pressione `Enter` para escolher
`JOGAR` ou clique na opção. Durante o duelo, a música de Gundyr é reproduzida
em loop a partir de `ost/Iudex Gundyr (Vorbis).ogg`. Essa cópia foi convertida
para Ogg Vorbis porque o arquivo original em Opus não abre no Pygame.

A opção `CHEATS` permite ajustar a vida e o multiplicador de dano do jogador
para testes. Use as setas ou `W/A/S/D` para navegar e alterar os valores, `R`
para restaurar o padrão e `Esc` para voltar ao menu principal.

Ao gerar o executável, inclua a música junto dos sprites:

```powershell
pyinstaller --noconfirm --clean --windowed --name AshenTrial --add-data "assets;assets" --add-data "ost/Iudex Gundyr (Vorbis).ogg;ost" main.py
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
| Interagir com fogueira / névoa | `G` |
| Mostrar ou ocultar ajuda | `H` |
| Mostrar ou ocultar hitboxes | `F3` |
| Pausar / abrir menu de pausa | `Esc` |
| Renascer / retornar após o fim | `R` |

No menu de pausa, use as setas ou `W/S` para escolher entre continuar e voltar
ao menu principal; confirme com `Enter` ou clique na opção desejada.

O jogador tem vida, stamina, combo, ataque forte, cura, pulo, rolamento com invencibilidade, defesa direcional e aparo. Ao pressionar `E`, ele saca e bebe o Estus; comandos do jogador não cancelam a animação, mas um ataque inimigo pode interrompê-la. A cura só é aplicada no momento do gole. Segurar `F` bloqueia golpes que chegam pela frente e consome stamina; ataques pelas costas ignoram o escudo. O chefe possui golpes com preparação e recuperação mais longas, recuos, investida, salto, combos, variações de tempo, golpes de área e uma segunda fase mais agressiva.

O HUD também registra as almas recebidas ao derrotar Hollows e Gundyr. As hitboxes podem ser ativadas com `F3`: azul para o jogador, laranja para inimigos, verde para ataques do jogador e vermelho para ataques inimigos.

## Animações

Todas as animações do cavaleiro e os movimentos largos do chefe usam uma fonte independente por movimento em `assets/source_v5/`, organizada em uma grade invisível 5×2. O exportador transforma cada fonte em uma tira de dez células isoladas em `assets/animations_v5/`, com margem de segurança, botas completas e linha de chão normalizada. Assim nenhuma espada, alabarda ou parte dos pés invade o quadro vizinho.

- Cavaleiro: idle, corrida, rolamento, defesa, beber Estus, morte com pose final deitada, dois ataques leves e dois ataques fortes.
- Iudex Gundyr: identidade alta e assimétrica inspirada na referência, alabarda consistente, idle separado, caminhada com passos alternados, duas varreduras, duas estocadas, golpe vertical e movimentos especiais.
- Hollows: sete PNGs de animação próprios com dez personagens completos cada (idle, caminhada, corrida/perseguição, ataque, dano, stagger e morte). As artes completas ficam em `assets/source_animations_v4/`; `tools/prepare_hollow_animations.py` apenas reorganiza quadros inteiros no formato horizontal usado pelo jogo, sem montar ou recortar partes do corpo.

Os atlases-fonte antigos ficam em `assets/hero_v3_atlas.png` e `assets/gundyr_v3_atlas.png`. Para reexportá-los, execute `py prepare_sprites.py`. Para reexportar as animações independentes corrigidas, execute `py prepare_independent_sprites.py`.
