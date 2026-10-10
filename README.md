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

As animações do cavaleiro e os golpes do chefe usam uma fonte independente por movimento em `assets/source_v5/`, organizada em uma grade invisível 5×2. O exportador transforma cada fonte em células isoladas em `assets/animations_v5/`, com margem de segurança, botas completas e linha de chão normalizada. A nova caminhada do Gundyr usa desenhos próprios em `assets/source_v6/gundyr_walk.png`, exportados como **um PNG por quadro** em `assets/animations_v6/gundyr_walk/`. O jogo prioriza esses arquivos individuais, que não podem capturar pedaços de um quadro vizinho.

- Cavaleiro: idle, corrida, rolamento, defesa, beber Estus, morte com pose final deitada, dois ataques leves e dois ataques fortes.
- Iudex Gundyr: identidade alta e assimétrica inspirada na referência, alabarda consistente, idle separado, caminhada com 16 poses novas desenhadas (100 ms por quadro, ciclo-base de 1,6 s), duas varreduras, duas estocadas, golpe vertical e movimentos especiais. A caminhada preserva a sequência das passadas ao parar e retomar o movimento.

Na caminhada, cada quadro é um desenho completo novo criado com geração de imagem, preservando o Gundyr, a armadura e a alabarda. O GIF e o diagrama de caminhada fornecidos pelo usuário foram usados como referência de movimento, sem trocar o personagem. O exportador não monta membros, não deforma poses e não cria quadros por optical flow ou crossfade: faz somente extração da silhueta completa, escala uniforme nos dois eixos e registro de origem/chão. A escala é calibrada por linha para compensar a diferença de tamanho na fonte gerada, sem alterar a anatomia nem igualar a altura de cada pose. Os 16 PNGs são reproduzidos diretamente. O arquivo `assets/source_v6/gundyr_walk.md` guarda os prompts e a origem da fonte selecionada. O relógio da animação continua acompanhando a distância percorrida e inverte ao recuar. Os scripts antigos `rig_gundyr_walk.py` e `interpolate_walk.py` ficam como histórico, mas não são chamados pelo jogo nem pelo comando de reexportação atual.

Para reexportar somente os novos desenhos (precisa apenas de Pygame):

```powershell
py prepare_drawn_walk.py
```

Os atlases-fonte antigos ficam em `assets/hero_v3_atlas.png` e `assets/gundyr_v3_atlas.png`. Para reexportá-los, execute `py prepare_sprites.py`. Para reexportar as animações independentes corrigidas:

```powershell
py -m pip install -r requirements-assets.txt
py prepare_independent_sprites.py
```

O exportador das fontes antigas usa NumPy; OpenCV era usado pelo método geométrico anterior. Nenhum deles é necessário para jogar, exportar a nova caminhada ou executar seus testes. Basta `requirements.txt`. Para verificar os novos PNGs, recorte, chão e reprodução, execute `py -m unittest discover -s tests -v`.
