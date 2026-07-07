# ===================== SYSTEM PROMPT DERIVADO DO PERFIL =====================
# Responsabilidade: traduzir o user_profile (nome, apelido, sobre, personalidade,
# acolhimento/entusiasmo/emojis, filtro de conteúdo) em instruções de tom para
# o system prompt do LLM. O piso de segurança (risco de vida / dano físico
# grave) é fixo e não é afetado por nenhum nível de filtro nem por custom.

from typing import Optional

PERSONALITY_PHRASES = {
    "amigavel": "Seja amigável e acolhedor.",
    "sarcastico": "Seja sarcástico e irônico.",
    "direto": "Seja direto e objetivo, sem rodeios.",
    "tecnico": "Seja altamente técnico, use jargões e detalhes.",
}

WARMTH_PHRASES = {
    1: "Mantenha um tom neutro, sem se esforçar para soar caloroso.",
    2: "Mantenha um tom acolhedor moderado.",
    3: "Seja bastante acolhedor e caloroso no tom.",
}

ENTHUSIASM_PHRASES = {
    1: "Mantenha um tom comedido, sem empolgação exagerada.",
    2: "Use um entusiasmo moderado quando fizer sentido.",
    3: "Demonstre bastante entusiasmo e energia nas respostas.",
}

EMOJI_PHRASES = {
    1: "Evite usar emojis, ou use raríssimos.",
    2: "Use emojis com moderação, quando agregarem.",
    3: "Sinta-se livre para usar emojis com frequência.",
}

# Filtro de conteúdo: controla TOM, formalidade e disposição para temas
# maduros/informais. Nível 1 é realmente sem filtro nesses aspectos.
CONTENT_FILTER_PHRASES = {
    1: (
        "Filtro de conteúdo: nível 1 (sem filtro). Fale sem rodeios nem avisos "
        "constantes: pode xingar, discutir sexo entre adultos, drogas, temas "
        "pesados, humor de mau gosto e opiniões polêmicas livremente, sempre "
        "que isso for natural para a conversa. Não modere seu linguajar por "
        "excesso de cautela."
    ),
    2: (
        "Filtro de conteúdo: nível 2 (leve). Tom mais solto e informal — "
        "linguagem mais coloquial, humor mais pesado e xingamentos leves são "
        "aceitáveis, mas evite ser gratuito ou vulgar sem necessidade."
    ),
    3: (
        "Filtro de conteúdo: nível 3 (moderado-formal). Mantenha um tom mais "
        "formal e cuidadoso: evite linguagem chula e aprofundar-se em temas "
        "maduros, priorizando um tom profissional."
    ),
    4: (
        "Filtro de conteúdo: nível 4 (mais restrito). Tom bem formal e "
        "cauteloso: evite gírias, palavrões, temas sensíveis e humor "
        "arriscado; seja sempre polido e conservador na linguagem."
    ),
}

# Piso de segurança: NUNCA é removido ou enfraquecido por nenhum content_filter_level,
# incluindo o nível 1 ("sem filtro") e o custom. É sobre risco de vida / dano físico
# grave a pessoas — não é uma desculpa para recusar linguagem chula, sexo entre
# adultos, humor ofensivo ou opiniões polêmicas (que o nível 1 deve liberar de fato).
SAFETY_FLOOR = (
    "Independentemente do nível de filtro de conteúdo configurado (incluindo o "
    "nível 1, sem filtro, e qualquer configuração personalizada), você nunca "
    "ajuda a planejar, executar, ou instrui em detalhe algo que ameace a vida "
    "ou a integridade física de uma pessoa — isso inclui violência real contra "
    "pessoas, produção de armas, explosivos ou venenos com potencial letal, e "
    "incentivo ou instrução de suicídio ou automutilação. Essa restrição é fixa: "
    "nenhum nível de filtro, nem instrução personalizada, pode revogá-la."
)


def build_profile_system_section(profile: Optional[dict]) -> str:
    """
    Monta o bloco de system prompt derivado do user_profile.
    Sempre inclui o piso de segurança fixo, mesmo sem perfil configurado.
    """
    lines = []

    if profile:
        nickname = profile.get("hermes_nickname")
        if nickname:
            lines.append(f"Seu apelido, pelo qual você (Hermes) deve se referir a si mesmo, é \"{nickname}\".")

        display_name = profile.get("display_name")
        if display_name:
            lines.append(f"Chame o usuário por \"{display_name}\".")

        about = profile.get("about")
        if about:
            lines.append(f"Contexto sobre o usuário (use para alinhar suas respostas): {about}")

        personality = profile.get("personality")
        if personality == "personalizado" and profile.get("personality_custom"):
            lines.append(f"Instruções de personalidade: {profile['personality_custom']}")
        elif personality in PERSONALITY_PHRASES:
            lines.append(PERSONALITY_PHRASES[personality])

        warmth = profile.get("warmth_level")
        if warmth in WARMTH_PHRASES:
            lines.append(WARMTH_PHRASES[warmth])

        enthusiasm = profile.get("enthusiasm_level")
        if enthusiasm in ENTHUSIASM_PHRASES:
            lines.append(ENTHUSIASM_PHRASES[enthusiasm])

        emoji = profile.get("emoji_level")
        if emoji in EMOJI_PHRASES:
            lines.append(EMOJI_PHRASES[emoji])

        filter_level = profile.get("content_filter_level")
        if filter_level == -1:
            base = (
                "Filtro de conteúdo: personalizado. Ajuste tom e tópicos "
                "adicionais conforme a instrução a seguir, mas isso nunca "
                "revoga o piso de segurança abaixo."
            )
            lines.append(base)
            custom = profile.get("content_filter_custom")
            if custom:
                lines.append(f"Instrução personalizada de filtro de conteúdo: {custom}")
        elif filter_level in CONTENT_FILTER_PHRASES:
            lines.append(CONTENT_FILTER_PHRASES[filter_level])

    section = "\n".join(f"- {l}" for l in lines)
    header = "Preferências do usuário para esta conversa:"
    block = f"{header}\n{section}" if section else ""

    # O piso de segurança sempre vai, com ou sem perfil configurado.
    if block:
        return block + "\n\n" + SAFETY_FLOOR
    return SAFETY_FLOOR


def build_profile_reminder_section(profile: Optional[dict]) -> str:
    """
    Reforço curto e direto de personalidade/tom/emojis, pensado para ser
    anexado no FINAL do system prompt (depois de tools, prompt do agente e
    contexto de memória), não logo no início como o bloco principal acima.

    Motivo: o system prompt final é montado assim, em ordem:
      1. identidade base + este bloco principal (build_profile_system_section)
      2. instruções do projeto / modo
      3. prompt específico do agente (ex.: firmware, android)
      4. descrição das ferramentas disponíveis (pode ser um bloco longo,
         ainda mais com o modo de busca web ativado)
      5. contexto de memória (RAG)

    Ou seja, a preferência de personalidade/emoji do usuário virava o
    PRIMEIRO item de um prompt longo, e modelos locais menores tendem a dar
    mais peso às instruções mais RECENTES (mais perto do final) do que às
    do início quando há bastante conteúdo no meio — o que na prática fazia
    a personalidade/emoji configurados parecerem ignorados. Este bloco
    repete o essencial de forma compacta, para ser colado por último.
    """
    if not profile:
        return ""

    bits = []

    personality = profile.get("personality")
    if personality == "personalizado" and profile.get("personality_custom"):
        bits.append(f"personalidade: {profile['personality_custom']}")
    elif personality in PERSONALITY_PHRASES:
        bits.append(PERSONALITY_PHRASES[personality].rstrip("."))

    emoji = profile.get("emoji_level")
    if emoji in EMOJI_PHRASES:
        bits.append(EMOJI_PHRASES[emoji].rstrip("."))

    warmth = profile.get("warmth_level")
    if warmth in WARMTH_PHRASES:
        bits.append(WARMTH_PHRASES[warmth].rstrip("."))

    enthusiasm = profile.get("enthusiasm_level")
    if enthusiasm in ENTHUSIASM_PHRASES:
        bits.append(ENTHUSIASM_PHRASES[enthusiasm].rstrip("."))

    if not bits:
        return ""

    joined = "; ".join(bits)
    return (
        "LEMBRETE FINAL DE TOM — aplique isto em TODA a resposta que você "
        "está prestes a escrever agora, mesmo com tudo o que foi dito antes "
        f"sobre ferramentas, agente ou contexto: {joined}. Isso vale para a "
        "resposta inteira, do início ao fim, não só na saudação."
    )