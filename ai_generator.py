"""
Módulo de Geração de Conteúdo por IA para Novelas.
Gera enredos, episódios, personagens e imagens para novelas turcas e mexicanas.
Suporta modo gratuito (templates) e modo OpenAI (GPT + DALL-E).
"""

import os
import random
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ─────────────────────────────────────────────
# TEMPLATES DE GERAÇÃO (Modo Gratuito)
# ─────────────────────────────────────────────

NOMES_FEMININOS_TURCOS = [
    "Ayşe", "Elif", "Zeynep", "Fatma", "Defne", "Nihan", "Eda", "Hande",
    "Selin", "Meryem", "Ceren", "Dilara", "Yasemin", "Leyla", "Esra",
    "Azra", "Melek", "Şebnem", "Cansu", "Beren",
]

NOMES_MASCULINOS_TURCOS = [
    "Kerem", "Can", "Serkan", "Miran", "Yaman", "Emir", "Burak", "Kaan",
    "Alp", "Ozan", "Cesur", "Ferit", "Onur", "Bariş", "Halil",
    "Çağatay", "Kivanç", "Engin", "Tolga", "Akın",
]

NOMES_FEMININOS_MEXICANOS = [
    "María", "Valentina", "Guadalupe", "Fernanda", "Catalina", "Isabela",
    "Rubí", "Soraya", "Teresa", "Mariana", "Paulina", "Regina", "Ximena",
    "Alejandra", "Lucía", "Camila", "Sofía", "Daniela", "Renata", "Andrea",
]

NOMES_MASCULINOS_MEXICANOS = [
    "Alejandro", "Santiago", "Diego", "Fernando", "Carlos", "Ricardo",
    "Eduardo", "Sebastián", "Rafael", "Javier", "Miguel", "Andrés",
    "Francisco", "Roberto", "Rodrigo", "Mateo", "Emiliano", "José Luis",
    "Arturo", "Héctor",
]

SOBRENOMES_TURCOS = [
    "Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Yıldız", "Özdemir",
    "Arslan", "Doğan", "Kılıç", "Aslan", "Koç", "Kurt", "Aydın", "Polat",
]

SOBRENOMES_MEXICANOS = [
    "García", "Rodríguez", "Hernández", "López", "Martínez", "González",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera",
    "De la Cruz", "Morales", "Castillo",
]

CENARIOS_TURCOS = [
    "uma mansão luxuosa em Istambul",
    "uma pequena vila na Capadócia",
    "o bazar histórico de Istambul",
    "uma empresa de moda em Ankara",
    "um palácio à beira do Bósforo",
    "um hospital moderno em Izmir",
    "uma fazenda de oliveiras no sul da Turquia",
    "um ateliê de arte em Bodrum",
    "uma universidade prestigiosa em Istambul",
    "um restaurante familiar em Antália",
]

CENARIOS_MEXICANOS = [
    "uma hacienda luxuosa em Guadalajara",
    "as ruas coloridas da Cidade do México",
    "uma empresa multinacional em Monterrey",
    "um rancho no campo de Jalisco",
    "uma mansão em Polanco",
    "um bairro humilde na periferia",
    "uma praia paradisíaca em Cancún",
    "uma vinícola em Valle de Guadalupe",
    "um hospital em Puebla",
    "uma escola de elite na capital",
]

CONFLITOS = [
    "um segredo do passado ameaça destruir tudo",
    "uma rivalidade familiar divide os amantes",
    "uma traição inesperada muda o rumo da história",
    "um casamento arranjado coloca tudo em risco",
    "uma herança milionária cria conflitos mortais",
    "um inimigo do passado retorna com sede de vingança",
    "uma identidade secreta é revelada",
    "um triângulo amoroso impossível de resolver",
    "uma conspiração empresarial ameaça a família",
    "uma doença grave testa o verdadeiro amor",
    "um filho perdido reaparece anos depois",
    "uma vingança planejada há anos é executada",
    "um acidente apaga memórias cruciais",
    "uma carta antiga revela a verdade sobre o passado",
    "um testamento contestado divide a família",
]

TEMAS = [
    "amor proibido", "vingança", "redenção", "ascensão social",
    "destino e fé", "poder e ambição", "sacrifício", "segunda chance",
    "identidade", "perdão", "lealdade", "família vs amor",
    "rico vs pobre", "passado sombrio", "recomeço",
]

REVIRAVOLTAS = [
    "O/A protagonista descobre que é adotado/a",
    "Um personagem dado como morto reaparece",
    "O vilão é na verdade o pai/mãe biológico/a",
    "Um casamento é interrompido por uma revelação chocante",
    "A protagonista descobre que está grávida",
    "Um documento perdido muda tudo",
    "O melhor amigo é na verdade o traidor",
    "Uma gêmea desconhecida aparece",
    "O protagonista perde a memória após um acidente",
    "Uma aliança inesperada entre inimigos",
    "Um sequestro muda o rumo da trama",
    "Uma confissão no leito de morte revela segredos",
    "O protagonista é falsamente acusado de um crime",
    "Um bebê trocado na maternidade",
    "Uma falência repentina inverte os papéis",
]

EMOCOES_CENA = [
    "com lágrimas nos olhos", "com um sorriso esperançoso",
    "tremendo de raiva", "em silêncio absoluto",
    "com determinação no olhar", "surpreso/a e sem palavras",
    "com o coração partido", "rindo de nervoso",
    "abraçando forte", "olhando pela janela com saudade",
]

DIALOGOS_ROMANTICOS = [
    "Eu nunca deixei de te amar, mesmo quando tentei com todas as minhas forças.",
    "Você é a razão pela qual eu acordo todos os dias com esperança.",
    "Não importa o que digam, meu coração sempre vai te escolher.",
    "Se tivesse que viver mil vidas, te encontraria em todas elas.",
    "Você me ensinou que amar de verdade é mais forte que qualquer obstáculo.",
    "Eu prefiro sofrer ao seu lado do que ser feliz sem você.",
    "Quando estou com você, o mundo inteiro desaparece.",
    "Meu amor por você é maior que qualquer segredo entre nós.",
]

DIALOGOS_DRAMA = [
    "Você destruiu tudo! Como espera que eu confie em você de novo?",
    "A verdade sempre aparece, e quando aparecer, você vai pagar por tudo!",
    "Eu sei o que você fez. E vou fazer você pagar por cada lágrima.",
    "Você não é quem diz ser. Eu descobri TUDO!",
    "Escolha: sua família ou seu orgulho. Não pode ter os dois.",
    "Eu te avisei. Agora aguente as consequências.",
    "Nunca mais vou deixar ninguém me machucar. Nunca mais!",
    "Esse segredo vai para o túmulo comigo. NINGUÉM pode saber!",
]

CLIFFHANGERS = [
    "Mas nesse exato momento, a porta se abre e surge a última pessoa que esperavam ver...",
    "O telefone toca. Do outro lado, uma voz sussurra algo que muda tudo...",
    "Ao abrir o envelope, seus olhos se arregalam. Era impossível...",
    "Enquanto isso, nas sombras, alguém observava tudo com um sorriso cruel...",
    "Uma explosão ecoa ao longe. O silêncio que se segue é ensurdecedor...",
    "A tela do celular acende com uma mensagem: 'Eu sei o que você fez.'",
    "Quando vira a foto, reconhece o rosto. Como isso era possível?",
    "O exame de DNA chega. Ao ler o resultado, o mundo para de girar...",
]


@dataclass
class Personagem:
    nome: str
    sobrenome: str
    idade: int
    papel: str
    descricao: str


@dataclass
class Episodio:
    numero: int
    titulo: str
    sinopse: str
    cena_principal: str
    dialogo: str
    cliffhanger: str


@dataclass
class Novela:
    titulo: str
    categoria: str
    sinopse: str
    tema: str
    cenario: str
    personagens: list
    total_episodios: int


# ─────────────────────────────────────────────
# GERADOR DE PERSONAGENS
# ─────────────────────────────────────────────
def gerar_personagem(categoria: str, papel: str) -> Personagem:
    if categoria == "turca":
        if papel in ["protagonista_f", "antagonista_f", "coadjuvante_f"]:
            nome = random.choice(NOMES_FEMININOS_TURCOS)
        else:
            nome = random.choice(NOMES_MASCULINOS_TURCOS)
        sobrenome = random.choice(SOBRENOMES_TURCOS)
    else:
        if papel in ["protagonista_f", "antagonista_f", "coadjuvante_f"]:
            nome = random.choice(NOMES_FEMININOS_MEXICANOS)
        else:
            nome = random.choice(NOMES_MASCULINOS_MEXICANOS)
        sobrenome = random.choice(SOBRENOMES_MEXICANOS)

    idade = random.randint(22, 45)

    descricoes = {
        "protagonista_f": [
            "Bela e determinada, luta por seus sonhos apesar das adversidades",
            "Inteligente e forte, esconde um passado doloroso",
            "Doce mas corajosa, nunca desiste de quem ama",
            "Independente e trabalhadora, busca justiça para sua família",
        ],
        "protagonista_m": [
            "Misterioso e protetor, carrega o peso de um segredo",
            "Rico e poderoso, mas com um coração bondoso",
            "Determinado e apaixonado, faz tudo por amor",
            "Forte e justo, luta contra sua própria família pela verdade",
        ],
        "antagonista_f": [
            "Manipuladora e invejosa, faz de tudo para destruir a protagonista",
            "Linda mas cruel, usa sua beleza como arma",
            "Ambiciosa sem limites, não aceita perder para ninguém",
            "Dissimulada e perigosa, planeja nas sombras",
        ],
        "antagonista_m": [
            "Poderoso e implacável, controla tudo ao seu redor",
            "Obcecado e possessivo, não aceita rejeição",
            "Corrupto e ganancioso, vende sua alma por poder",
            "Vingativo e calculista, espera o momento perfeito para atacar",
        ],
        "coadjuvante_f": [
            "Melhor amiga leal, sempre presente nos momentos difíceis",
            "Mãe protetora que faz de tudo pelos filhos",
            "Irmã mais velha sábia, dá os melhores conselhos",
        ],
        "coadjuvante_m": [
            "Melhor amigo fiel, oferece seu ombro e sua força",
            "Pai justo que luta para manter a família unida",
            "Irmão protetor que não mede esforços pela família",
        ],
    }

    descricao = random.choice(descricoes.get(papel, ["Personagem misterioso/a"]))

    return Personagem(
        nome=nome,
        sobrenome=sobrenome,
        idade=idade,
        papel=papel.replace("_f", "").replace("_m", ""),
        descricao=descricao,
    )


# ─────────────────────────────────────────────
# GERADOR DE NOVELA COMPLETA
# ─────────────────────────────────────────────
def gerar_novela(categoria: str = None) -> Novela:
    if categoria is None:
        categoria = random.choice(["turca", "mexicana"])

    tema = random.choice(TEMAS)
    cenario = random.choice(
        CENARIOS_TURCOS if categoria == "turca" else CENARIOS_MEXICANOS
    )
    conflito = random.choice(CONFLITOS)

    # Gerar personagens
    personagens = [
        gerar_personagem(categoria, "protagonista_f"),
        gerar_personagem(categoria, "protagonista_m"),
        gerar_personagem(categoria, "antagonista_f"),
        gerar_personagem(categoria, "antagonista_m"),
        gerar_personagem(categoria, "coadjuvante_f"),
        gerar_personagem(categoria, "coadjuvante_m"),
    ]

    # Gerar título
    titulos_base = {
        "turca": [
            f"O Segredo de {personagens[0].nome}",
            f"{personagens[0].nome} e {personagens[1].nome}: Amor Impossível",
            f"Nas Terras de {personagens[1].sobrenome}",
            f"A Promessa de {personagens[0].nome}",
            f"Entre Dois Mundos: {personagens[0].nome}",
            f"O Destino de {personagens[0].nome} {personagens[0].sobrenome}",
            f"Coração de {personagens[0].nome}",
            f"A Vingança dos {personagens[1].sobrenome}",
        ],
        "mexicana": [
            f"La Pasión de {personagens[0].nome}",
            f"{personagens[0].nome}: Amor y Venganza",
            f"El Secreto de los {personagens[1].sobrenome}",
            f"Corazón Salvaje: {personagens[0].nome}",
            f"{personagens[0].nome} — Destino de Mujer",
            f"La Herencia de los {personagens[1].sobrenome}",
            f"Amor Prohibido: {personagens[0].nome} y {personagens[1].nome}",
            f"El Precio del Amor",
        ],
    }

    titulo = random.choice(titulos_base[categoria])

    # Gerar sinopse
    sinopse = (
        f"Em {cenario}, {personagens[0].nome} {personagens[0].sobrenome} "
        f"({personagens[0].descricao.lower()}) cruza o caminho de "
        f"{personagens[1].nome} {personagens[1].sobrenome} "
        f"({personagens[1].descricao.lower()}). "
        f"O tema central é {tema}, mas {conflito}. "
        f"{personagens[2].nome} {personagens[2].sobrenome} "
        f"({personagens[2].descricao.lower()}) fará de tudo para separá-los, "
        f"enquanto {personagens[3].nome} {personagens[3].sobrenome} "
        f"({personagens[3].descricao.lower()}) trama nas sombras."
    )

    total_episodios = random.choice([40, 50, 60, 80, 100, 120])

    return Novela(
        titulo=titulo,
        categoria=categoria,
        sinopse=sinopse,
        tema=tema,
        cenario=cenario,
        personagens=personagens,
        total_episodios=total_episodios,
    )


# ─────────────────────────────────────────────
# GERADOR DE EPISÓDIOS
# ─────────────────────────────────────────────
def gerar_episodio(novela: Novela, numero: int) -> Episodio:
    personagens = novela.personagens
    protagonista_f = personagens[0]
    protagonista_m = personagens[1]
    antagonista_f = personagens[2]
    antagonista_m = personagens[3]

    # Título do episódio
    titulos_ep = [
        f"A Revelação",
        f"Noite de Tempestade",
        f"O Encontro",
        f"Mentiras e Verdades",
        f"O Preço do Silêncio",
        f"Corações em Conflito",
        f"A Decisão",
        f"Fantasmas do Passado",
        f"Um Novo Começo",
        f"A Emboscada",
        f"Entre o Amor e o Dever",
        f"Segredos Revelados",
        f"A Fuga",
        f"Destinos Cruzados",
        f"O Último Suspiro",
        f"Além das Aparências",
        f"A Promessa Quebrada",
        f"Nas Sombras",
        f"O Retorno",
        f"Fogo e Gelo",
    ]

    titulo = random.choice(titulos_ep)

    # Determinar fase da novela
    progresso = numero / novela.total_episodios
    if progresso < 0.2:
        fase = "introdução"
    elif progresso < 0.5:
        fase = "desenvolvimento"
    elif progresso < 0.8:
        fase = "clímax"
    else:
        fase = "desfecho"

    # Gerar sinopse do episódio baseado na fase
    sinopses_fase = {
        "introdução": [
            f"{protagonista_f.nome} chega a {novela.cenario} e conhece {protagonista_m.nome}. "
            f"A atração é imediata, mas {antagonista_f.nome} percebe e começa a tramar.",
            f"Um evento inesperado coloca {protagonista_f.nome} e {protagonista_m.nome} no mesmo caminho. "
            f"Enquanto isso, {antagonista_m.nome} observa tudo de longe.",
            f"{protagonista_f.nome} tenta reconstruir sua vida em {novela.cenario}. "
            f"Quando encontra {protagonista_m.nome}, sente que o destino os uniu.",
        ],
        "desenvolvimento": [
            f"A relação entre {protagonista_f.nome} e {protagonista_m.nome} se fortalece, "
            f"mas {antagonista_f.nome} descobre um segredo que pode destruir tudo. "
            f"{antagonista_m.nome} se alia a ela para separá-los.",
            f"{protagonista_m.nome} precisa fazer uma escolha impossível entre sua família "
            f"e {protagonista_f.nome}. {antagonista_f.nome} aproveita o momento de fraqueza.",
            f"Um evento do passado vem à tona e abala {protagonista_f.nome}. "
            f"{protagonista_m.nome} jura protegê-la, mas {antagonista_m.nome} tem outros planos.",
        ],
        "clímax": [
            f"A verdade finalmente é revelada! {protagonista_f.nome} descobre tudo sobre "
            f"{antagonista_m.nome}. A confrontação é inevitável e explosiva.",
            f"{antagonista_f.nome} executa seu plano final contra {protagonista_f.nome}. "
            f"{protagonista_m.nome} corre contra o tempo para salvá-la.",
            f"Tudo parece perdido. {protagonista_f.nome} e {protagonista_m.nome} são separados "
            f"pela última armadilha de {antagonista_f.nome} e {antagonista_m.nome}.",
        ],
        "desfecho": [
            f"Após tanta luta, {protagonista_f.nome} e {protagonista_m.nome} finalmente "
            f"vencem os obstáculos. {antagonista_f.nome} paga por seus crimes.",
            f"O amor verdadeiro triunfa. {protagonista_f.nome} e {protagonista_m.nome} "
            f"começam uma nova vida juntos, livres do passado.",
            f"A justiça é feita. {antagonista_m.nome} é preso e {protagonista_f.nome} "
            f"encontra a paz que tanto buscava ao lado de {protagonista_m.nome}.",
        ],
    }

    sinopse = random.choice(sinopses_fase[fase])

    # Cena principal
    emocao = random.choice(EMOCOES_CENA)
    cena = f"{protagonista_f.nome} está {emocao} em {novela.cenario}."

    # Diálogo
    if fase in ("introdução", "desfecho"):
        dialogo_base = random.choice(DIALOGOS_ROMANTICOS)
    else:
        dialogo_base = random.choice(DIALOGOS_DRAMA)

    dialogo = f"💬 {protagonista_f.nome if random.random() > 0.5 else protagonista_m.nome}: \"{dialogo_base}\""

    # Cliffhanger
    cliffhanger = random.choice(CLIFFHANGERS) if fase != "desfecho" else ""

    return Episodio(
        numero=numero,
        titulo=titulo,
        sinopse=sinopse,
        cena_principal=cena,
        dialogo=dialogo,
        cliffhanger=cliffhanger,
    )


# ─────────────────────────────────────────────
# GERADOR DE IMAGEM (PROMPT)
# ─────────────────────────────────────────────
def gerar_prompt_imagem(novela: Novela, tipo: str = "capa") -> str:
    protagonista_f = novela.personagens[0]
    protagonista_m = novela.personagens[1]

    if tipo == "capa":
        estilo = "cinematic, dramatic lighting, telenovela style"
        if novela.categoria == "turca":
            prompt = (
                f"A beautiful Turkish woman and a handsome Turkish man, "
                f"romantic scene in {novela.cenario.replace('uma ', 'a ').replace('um ', 'a ')}, "
                f"dramatic sunset, {estilo}, 4K quality, poster style"
            )
        else:
            prompt = (
                f"A beautiful Latin woman and a handsome Mexican man, "
                f"passionate scene in {novela.cenario.replace('uma ', 'a ').replace('um ', 'a ')}, "
                f"warm colors, {estilo}, 4K quality, poster style"
            )
    elif tipo == "cena":
        cenarios_img = [
            "luxurious mansion interior, dramatic lighting",
            "beautiful garden at sunset",
            "city skyline at night, romantic atmosphere",
            "traditional village, rustic charm",
            "elegant ballroom, chandeliers",
        ]
        prompt = f"Telenovela scene, {random.choice(cenarios_img)}, cinematic, dramatic, 4K"
    else:
        prompt = f"Portrait of a character, telenovela style, dramatic lighting, cinematic, 4K"

    return prompt


# ─────────────────────────────────────────────
# INTEGRAÇÃO COM OPENAI (Opcional)
# ─────────────────────────────────────────────
async def gerar_com_openai(prompt: str, tipo: str = "texto") -> str:
    """Gera conteúdo usando OpenAI API (requer OPENAI_API_KEY)."""
    if not OPENAI_API_KEY:
        return ""

    try:
        import httpx

        if tipo == "texto":
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {
                                "role": "system",
                                "content": "Você é um roteirista de novelas especializado em novelas turcas e mexicanas. Escreva em português brasileiro.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.8,
                    },
                )
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        elif tipo == "imagem":
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                    },
                )
            data = resp.json()
            return data["data"][0]["url"]

    except Exception as e:
        logger.warning(f"Erro OpenAI ({tipo}): {e}")
        return ""

    return ""


# ─────────────────────────────────────────────
# FORMATAÇÃO PARA TELEGRAM
# ─────────────────────────────────────────────
def formatar_novela_telegram(novela: Novela) -> str:
    emoji_cat = "🇹🇷" if novela.categoria == "turca" else "🇲🇽"
    cat_nome = "Turca" if novela.categoria == "turca" else "Mexicana"

    texto = (
        f"🎬 <b>NOVA NOVELA GERADA POR IA!</b>\n\n"
        f"{emoji_cat} <b>{novela.titulo}</b>\n"
        f"📺 Categoria: {cat_nome}\n"
        f"🎭 Tema: {novela.tema.capitalize()}\n"
        f"📍 Cenário: {novela.cenario.capitalize()}\n"
        f"📋 Episódios: {novela.total_episodios}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📖 <b>Sinopse:</b>\n{novela.sinopse}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Personagens:</b>\n"
    )

    for p in novela.personagens:
        papel_emoji = {
            "protagonista": "⭐",
            "antagonista": "😈",
            "coadjuvante": "👤",
        }
        emoji = papel_emoji.get(p.papel, "👤")
        texto += f"{emoji} <b>{p.nome} {p.sobrenome}</b> ({p.idade} anos) — {p.descricao}\n"

    return texto


def formatar_episodio_telegram(episodio: Episodio, novela_titulo: str) -> str:
    texto = (
        f"📺 <b>{novela_titulo}</b>\n"
        f"🎬 <b>Episódio {episodio.numero}: {episodio.titulo}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📖 <b>Sinopse:</b>\n{episodio.sinopse}\n\n"
        f"🎭 <b>Cena Principal:</b>\n{episodio.cena_principal}\n\n"
        f"🗣️ <b>Diálogo Destaque:</b>\n{episodio.dialogo}\n"
    )

    if episodio.cliffhanger:
        texto += (
            f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Fim do Episódio:</b>\n"
            f"<i>{episodio.cliffhanger}</i>\n"
        )

    texto += f"\n💡 <i>Conteúdo gerado por IA — Novelas Play</i>"

    return texto


# ─────────────────────────────────────────────
# GERADOR DE MINI-SÉRIE (5 episódios resumidos)
# ─────────────────────────────────────────────
def gerar_mini_serie(categoria: str = None) -> tuple:
    """Gera uma novela com 5 episódios resumidos para prévia."""
    novela = gerar_novela(categoria)
    episodios = []

    pontos_chave = [1, int(novela.total_episodios * 0.3),
                    int(novela.total_episodios * 0.5),
                    int(novela.total_episodios * 0.8),
                    novela.total_episodios]

    for ep_num in pontos_chave:
        ep = gerar_episodio(novela, ep_num)
        episodios.append(ep)

    return novela, episodios
