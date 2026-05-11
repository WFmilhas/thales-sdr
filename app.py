import os
import json
from flask import Flask, request, jsonify
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Memória de conversa por usuário (em produção usar Redis ou banco)
conversations = {}

SYSTEM_PROMPT = """Você é um assistente de vendas especializado nas mentorias do Thales Damasceno. 
Seu objetivo é qualificar leads e direcioná-los para a mentoria certa.

## PRODUTOS QUE VOCÊ REPRESENTA

### 1. Mentoria de Milhas
- Ensina a acumular e usar milhas aéreas para viajar de graça ou muito barato
- Resultado: viajar nacional e internacional pagando muito menos (econômica e executiva)
- Público: pessoas que querem viajar mais gastando menos, iniciantes e intermediários em milhas
- Diferenciais: método prático, acesso ao grupo de alertas de passagens baratas, suporte direto

### 2. Grupo Black (CCM)
- Nível avançado — para quem já conhece milhas e quer maximizar
- Resultado: acesso a passagens premium, alertas exclusivos, estratégias avançadas de acúmulo
- Público: pessoas que já acumulam milhas e querem o próximo nível
- Diferenciais: alertas em tempo real, passagens executivas e primeira classe, comunidade exclusiva

## SEU COMPORTAMENTO

1. QUALIFIQUE antes de empurrar produto. Faça no máximo 2 perguntas antes de indicar.
2. PERGUNTAS DE QUALIFICAÇÃO principais:
   - "Você já acumula milhas ou está começando do zero?"
   - "Você já viajou usando milhas alguma vez?"
   - "Qual o seu maior objetivo: viajar mais barato ou voar na executiva/primeira classe?"

3. DIRECIONAMENTO:
   - Iniciante / nunca usou milhas → Mentoria de Milhas
   - Já usa milhas e quer mais → Grupo Black
   - Dúvida → perguntar mais uma vez e decidir

4. FECHAMENTO: Quando identificar o produto certo, apresente de forma entusiasmada e pergunte se quer saber como entrar.

5. TOM: Amigável, empolgante, direto. Sem ser robótico. Use emojis com moderação. ✈️🎯

6. LIMITE: Você não tem acesso a preços ou datas de turmas. Se perguntarem, diga que vai conectar com o Thales para detalhes finais.

7. NUNCA invente informações sobre preços, datas ou garantias específicas.

Responda sempre em português brasileiro, de forma natural e conversacional.
Seja conciso — respostas curtas funcionam melhor no Instagram. Máximo 3-4 linhas por mensagem."""


def get_ai_response(user_id: str, user_message: str) -> str:
    """Processa mensagem do usuário e retorna resposta da IA."""
    
    if user_id not in conversations:
        conversations[user_id] = []
    
    conversations[user_id].append({
        "role": "user",
        "content": user_message
    })
    
    # Manter apenas últimas 10 mensagens para não estourar contexto
    history = conversations[user_id][-10:]
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=history
    )
    
    assistant_message = response.content[0].text
    
    conversations[user_id].append({
        "role": "assistant",
        "content": assistant_message
    })
    
    return assistant_message


@app.route("/webhook", methods=["POST"])
def webhook():
    """Endpoint principal recebendo mensagens do ManyChat."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Payload vazio"}), 400
        
        # ManyChat envia o campo 'last_input_text' com a mensagem do usuário
        user_message = data.get("last_input_text", "")
        user_id = data.get("id", "default_user")
        first_name = data.get("first_name", "")
        
        if not user_message:
            # Primeira mensagem / sem texto — mensagem de boas-vindas
            user_message = f"Olá, meu nome é {first_name}" if first_name else "Olá"
        
        ai_response = get_ai_response(str(user_id), user_message)
        
        # Formato de resposta que o ManyChat espera
        return jsonify({
            "version": "v2",
            "content": {
                "messages": [
                    {
                        "type": "text",
                        "text": ai_response
                    }
                ],
                "actions": [],
                "quick_replies": []
            }
        })
    
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({
            "version": "v2",
            "content": {
                "messages": [
                    {
                        "type": "text",
                        "text": "Oi! Tive um probleminha aqui. Pode repetir sua mensagem? 😊"
                    }
                ]
            }
        }), 200


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de verificação de saúde do servidor."""
    return jsonify({"status": "ok", "message": "SDR Thales ativo"}), 200


@app.route("/reset/<user_id>", methods=["POST"])
def reset_conversation(user_id: str):
    """Reseta conversa de um usuário específico."""
    if user_id in conversations:
        del conversations[user_id]
    return jsonify({"status": "ok", "message": f"Conversa de {user_id} resetada"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
