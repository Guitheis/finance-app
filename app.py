import streamlit as st
import pandas as pd
import os
from datetime import date, timedelta

st.set_page_config(page_title="Financeiro Premium", layout="wide")

TRANSACOES_FILE = "transacoes.csv"
PROVISOES_FILE = "provisoes.csv"
SALDOS_FILE = "saldos.csv"
EMPRESTIMOS_FILE = "emprestimos.csv"

def money(v):
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def auto_categoria(texto):
    texto = str(texto).lower()

    regras = {
        "Alimentação": ["ifood", "mercado", "restaurante", "pizza", "lanche", "comida", "padaria"],
        "Moradia": ["aluguel", "condominio", "condomínio"],
        "Transporte": ["uber", "99", "gasolina", "combustivel", "combustível"],
        "Contas": ["luz", "agua", "água", "internet", "telefone", "energia", "celular"],
        "Lazer": ["bar", "cinema", "festa", "show", "balada", "ingresso"],
        "Saúde": ["farmacia", "farmácia", "consulta", "remedio", "remédio"],
        "Assinaturas": ["netflix", "spotify", "prime", "disney", "globoplay", "youtube"],
        "Receita": ["salario", "salário", "pix recebido", "recebimento", "bonus", "bônus"]
    }

    for categoria, palavras in regras.items():
        if any(p in texto for p in palavras):
            return categoria

    return "Outros"

def criar_csv(caminho, colunas, inicial=None):
    if not os.path.exists(caminho):
        if inicial:
            pd.DataFrame(inicial).to_csv(caminho, index=False)
        else:
            pd.DataFrame(columns=colunas).to_csv(caminho, index=False)

    df = pd.read_csv(caminho)

    for c in colunas:
        if c not in df.columns:
            df[c] = ""

    df = df[colunas]
    df.to_csv(caminho, index=False)
    return df

def preparar(df):
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    return df

def salvar(df, arquivo):
    df.to_csv(arquivo, index=False)

def gerar_sugestoes_ia(transacoes, provisoes, saldo_total, saldo_previsto):
    sugestoes = []

    despesas = transacoes[transacoes["tipo"] == "Saída"].copy()

    if despesas.empty:
        sugestoes.append(("info", "Ainda não há despesas suficientes para análise. Lance alguns gastos para a IA começar a sugerir cortes."))
        return sugestoes

    total_despesas = despesas["valor"].sum()
    por_categoria = despesas.groupby("categoria")["valor"].sum().sort_values(ascending=False)

    maior_categoria = por_categoria.index[0]
    maior_valor = por_categoria.iloc[0]
    peso_maior = maior_valor / total_despesas if total_despesas > 0 else 0

    sugestoes.append((
        "principal",
        f"Seu maior gasto está em **{maior_categoria}**, com {money(maior_valor)}. Isso representa {peso_maior:.1%} das suas saídas."
    ))

    categorias_cortaveis = ["Alimentação", "Lazer", "Outros", "Assinaturas", "Transporte"]

    for categoria in por_categoria.index:
        valor = por_categoria.loc[categoria]

        if categoria in categorias_cortaveis:
            corte_10 = valor * 0.10
            corte_15 = valor * 0.15
            sugestoes.append((
                "corte",
                f"Em **{categoria}**, uma redução conservadora de 10% economizaria {money(corte_10)}. Um corte mais agressivo de 15% economizaria {money(corte_15)}."
            ))

    gastos_altos = despesas[despesas["valor"] >= despesas["valor"].mean() * 1.8].sort_values("valor", ascending=False)

    if not gastos_altos.empty:
        top = gastos_altos.iloc[0]
        sugestoes.append((
            "alerta",
            f"Gasto fora da média detectado: **{top['descricao']}**, categoria **{top['categoria']}**, valor {money(top['valor'])}. Vale revisar se foi necessário ou recorrente."
        ))

    if "descricao" in despesas.columns:
        recorrentes = (
            despesas.groupby("descricao")["valor"]
            .agg(["count", "sum"])
            .sort_values("sum", ascending=False)
        )
        recorrentes = recorrentes[recorrentes["count"] >= 2]

        if not recorrentes.empty:
            desc = recorrentes.index[0]
            valor_rec = recorrentes.iloc[0]["sum"]
            qtd = int(recorrentes.iloc[0]["count"])
            sugestoes.append((
                "recorrente",
                f"Despesa recorrente identificada: **{desc}** apareceu {qtd} vezes, somando {money(valor_rec)}. Pode ser assinatura, hábito ou gasto repetido."
            ))

    provisoes_abertas = provisoes[provisoes["status"] != "Realizada"].copy()

    if not provisoes_abertas.empty:
        futuras_saidas = provisoes_abertas[provisoes_abertas["tipo"] == "Saída"]["valor"].sum()
        futuras_entradas = provisoes_abertas[provisoes_abertas["tipo"] == "Entrada"]["valor"].sum()

        if futuras_saidas > futuras_entradas:
            gap = futuras_saidas - futuras_entradas
            sugestoes.append((
                "previsao",
                f"Suas saídas previstas superam suas entradas previstas em {money(gap)}. Recomendo reduzir gastos variáveis antes do vencimento dessas provisões."
            ))

    if saldo_previsto < 0:
        necessidade = abs(saldo_previsto)
        sugestoes.append((
            "critico",
            f"Seu saldo previsto fica negativo em {money(necessidade)}. Prioridade: cortar gastos variáveis e adiar despesas não essenciais."
        ))
    elif saldo_previsto < saldo_total * 0.25:
        sugestoes.append((
            "atencao",
            "Seu saldo previsto ficará apertado. Recomendo preservar caixa e evitar novas despesas variáveis até estabilizar."
        ))

    return sugestoes

trans_cols = ["data", "tipo", "descricao", "categoria", "valor", "origem"]
prov_cols = ["data", "tipo", "descricao", "categoria", "valor", "origem", "tipo_provisao", "status"]
saldos_cols = ["cc", "beneficio"]
emp_cols = ["data", "nome", "valor", "status", "observacao"]

transacoes = preparar(criar_csv(TRANSACOES_FILE, trans_cols))
provisoes = preparar(criar_csv(PROVISOES_FILE, prov_cols))
saldos = criar_csv(SALDOS_FILE, saldos_cols, [{"cc": 0.0, "beneficio": 0.0}])
emprestimos = preparar(criar_csv(EMPRESTIMOS_FILE, emp_cols))

saldos["cc"] = pd.to_numeric(saldos["cc"], errors="coerce").fillna(0.0)
saldos["beneficio"] = pd.to_numeric(saldos["beneficio"], errors="coerce").fillna(0.0)

st.sidebar.title("🏦 Financeiro")
menu = st.sidebar.radio(
    "Menu",
    ["Dashboard", "Movimentar", "Provisões", "Empréstimos", "Saldos", "IA de Cortes", "Históricos"]
)

auto_realizar = st.sidebar.checkbox("Realizar provisões vencidas automaticamente", value=False)

if auto_realizar:
    vencidas = provisoes[
        (provisoes["status"] != "Realizada") &
        (pd.to_datetime(provisoes["data"], errors="coerce").dt.date <= date.today())
    ]

    if not vencidas.empty:
        novas = vencidas[["data", "tipo", "descricao", "categoria", "valor", "origem"]].copy()
        transacoes = pd.concat([transacoes, novas], ignore_index=True)
        provisoes.loc[vencidas.index, "status"] = "Realizada"
        salvar(transacoes, TRANSACOES_FILE)
        salvar(provisoes, PROVISOES_FILE)
        st.sidebar.success(f"{len(vencidas)} provisão(ões) realizada(s).")
        st.rerun()

cc_base = float(saldos["cc"].iloc[0])
beneficio_base = float(saldos["beneficio"].iloc[0])

entradas_cc = transacoes[(transacoes["tipo"] == "Entrada") & (transacoes["origem"] == "Conta Corrente")]["valor"].sum()
saidas_cc = transacoes[(transacoes["tipo"] == "Saída") & (transacoes["origem"] == "Conta Corrente")]["valor"].sum()

entradas_b = transacoes[(transacoes["tipo"] == "Entrada") & (transacoes["origem"] == "Benefício")]["valor"].sum()
saidas_b = transacoes[(transacoes["tipo"] == "Saída") & (transacoes["origem"] == "Benefício")]["valor"].sum()

saldo_cc = cc_base + entradas_cc - saidas_cc
saldo_beneficio = beneficio_base + entradas_b - saidas_b
saldo_total = saldo_cc + saldo_beneficio

provisoes_abertas = provisoes[provisoes["status"] != "Realizada"]
prev_entradas = provisoes_abertas[provisoes_abertas["tipo"] == "Entrada"]["valor"].sum()
prev_saidas = provisoes_abertas[provisoes_abertas["tipo"] == "Saída"]["valor"].sum()
saldo_previsto = saldo_total + prev_entradas - prev_saidas

emprestimos_abertos = emprestimos[emprestimos["status"] == "Aberto"]
total_emprestado = emprestimos_abertos["valor"].sum()
patrimonio_total = saldo_total + total_emprestado

if menu == "Dashboard":
    st.title("💳 Dashboard Financeiro")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Conta Corrente", money(saldo_cc))
    c2.metric("Benefício", money(saldo_beneficio))
    c3.metric("Saldo Atual", money(saldo_total))
    c4.metric("Saldo Previsto", money(saldo_previsto))

    if saldo_previsto < 0:
        st.error("⚠️ Alerta: seu caixa ficará negativo pelas provisões.")
    elif saldo_previsto < saldo_total * 0.25:
        st.warning("⚠️ Atenção: saldo previsto apertado.")
    else:
        st.success("✅ Caixa saudável pelas provisões atuais.")

    c5, c6 = st.columns(2)
    c5.metric("Emprestado na rua", money(total_emprestado))
    c6.metric("Patrimônio total", money(patrimonio_total))

    st.subheader("📈 Projeção de caixa - próximos 30 dias")

    fim = date.today() + timedelta(days=30)
    futuras = provisoes_abertas[
        (pd.to_datetime(provisoes_abertas["data"], errors="coerce").dt.date >= date.today()) &
        (pd.to_datetime(provisoes_abertas["data"], errors="coerce").dt.date <= fim)
    ].copy()

    if not futuras.empty:
        futuras = futuras.sort_values("data")
        futuras["impacto"] = futuras.apply(lambda x: x["valor"] if x["tipo"] == "Entrada" else -x["valor"], axis=1)
        futuras["saldo_projetado"] = saldo_total + futuras["impacto"].cumsum()
        st.line_chart(futuras.set_index("data")["saldo_projetado"])
        st.dataframe(futuras[["data", "tipo", "descricao", "categoria", "valor", "origem", "saldo_projetado"]], use_container_width=True)
    else:
        st.info("Sem provisões nos próximos 30 dias.")

elif menu == "Movimentar":
    st.title("➕ Nova movimentação")

    col1, col2 = st.columns(2)

    with col1:
        tipo = st.radio("Tipo", ["Entrada", "Saída"])
        valor = st.number_input("Valor", min_value=0.0, step=10.0)
        descricao = st.text_input("Descrição")

    with col2:
        categoria_manual = st.text_input("Categoria manual (opcional)")
        origem = st.selectbox("Origem", ["Conta Corrente", "Benefício"])
        data_lanc = st.date_input("Data", date.today())

    categoria = categoria_manual if categoria_manual else auto_categoria(descricao)

    if st.button("Salvar movimentação"):
        nova = pd.DataFrame([{
            "data": data_lanc,
            "tipo": tipo,
            "descricao": descricao,
            "categoria": categoria,
            "valor": valor,
            "origem": origem
        }])
        transacoes = pd.concat([transacoes, nova], ignore_index=True)
        salvar(transacoes, TRANSACOES_FILE)
        st.success(f"Movimentação salva em: {categoria}")
        st.rerun()

elif menu == "Provisões":
    st.title("📅 Provisões")

    col1, col2 = st.columns(2)

    with col1:
        tipo_p = st.radio("Tipo", ["Entrada", "Saída"], key="tipo_p")
        valor_p = st.number_input("Valor previsto", min_value=0.0, step=10.0)
        descricao_p = st.text_input("Descrição da provisão")

    with col2:
        categoria_manual_p = st.text_input("Categoria manual (opcional)", key="cat_p")
        origem_p = st.selectbox("Origem", ["Conta Corrente", "Benefício"], key="orig_p")
        tipo_provisao = st.selectbox("Tipo da provisão", ["Fixa", "Variável"])
        data_p = st.date_input("Data prevista", date.today())

    categoria_p = categoria_manual_p if categoria_manual_p else auto_categoria(descricao_p)

    if st.button("Salvar provisão"):
        nova = pd.DataFrame([{
            "data": data_p,
            "tipo": tipo_p,
            "descricao": descricao_p,
            "categoria": categoria_p,
            "valor": valor_p,
            "origem": origem_p,
            "tipo_provisao": tipo_provisao,
            "status": "Aberta"
        }])
        provisoes = pd.concat([provisoes, nova], ignore_index=True)
        salvar(provisoes, PROVISOES_FILE)
        st.success("Provisão salva.")
        st.rerun()

    st.subheader("🔁 Transformar provisão em transação")

    abertas = provisoes[provisoes["status"] != "Realizada"]

    if not abertas.empty:
        idx = st.selectbox(
            "Selecione",
            abertas.index,
            format_func=lambda i: f"{provisoes.loc[i,'data']} | {provisoes.loc[i,'descricao']} | {money(provisoes.loc[i,'valor'])}"
        )

        if st.button("Transformar em transação"):
            p = provisoes.loc[idx]

            nova = pd.DataFrame([{
                "data": date.today(),
                "tipo": p["tipo"],
                "descricao": p["descricao"],
                "categoria": p["categoria"],
                "valor": p["valor"],
                "origem": p["origem"]
            }])

            transacoes = pd.concat([transacoes, nova], ignore_index=True)
            provisoes.loc[idx, "status"] = "Realizada"

            salvar(transacoes, TRANSACOES_FILE)
            salvar(provisoes, PROVISOES_FILE)

            st.success("Provisão realizada.")
            st.rerun()

    st.dataframe(provisoes.sort_values("data"), use_container_width=True)

elif menu == "Empréstimos":
    st.title("💸 Dinheiro emprestado")

    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome")
        valor_emp = st.number_input("Valor emprestado", min_value=0.0, step=10.0)

    with col2:
        status = st.selectbox("Status", ["Aberto", "Pago"])
        obs = st.text_input("Observação")
        data_emp = st.date_input("Data", date.today())

    if st.button("Registrar empréstimo"):
        novo = pd.DataFrame([{
            "data": data_emp,
            "nome": nome,
            "valor": valor_emp,
            "status": status,
            "observacao": obs
        }])
        emprestimos = pd.concat([emprestimos, novo], ignore_index=True)
        salvar(emprestimos, EMPRESTIMOS_FILE)
        st.success("Empréstimo registrado.")
        st.rerun()

    abertos = emprestimos[emprestimos["status"] == "Aberto"]

    if not abertos.empty:
        idx_emp = st.selectbox(
            "Marcar como pago",
            abertos.index,
            format_func=lambda i: f"{emprestimos.loc[i,'nome']} | {money(emprestimos.loc[i,'valor'])}"
        )

        if st.button("Marcar pago"):
            emprestimos.loc[idx_emp, "status"] = "Pago"
            salvar(emprestimos, EMPRESTIMOS_FILE)
            st.success("Pago.")
            st.rerun()

    st.metric("Total em aberto", money(total_emprestado))
    st.dataframe(emprestimos.sort_values("data", ascending=False), use_container_width=True)

elif menu == "Saldos":
    st.title("⚙️ Saldos iniciais")

    novo_cc = st.number_input("Conta Corrente", value=cc_base, step=10.0)
    novo_b = st.number_input("Benefício", value=beneficio_base, step=10.0)

    if st.button("Salvar saldos"):
        saldos = pd.DataFrame([{"cc": novo_cc, "beneficio": novo_b}])
        salvar(saldos, SALDOS_FILE)
        st.success("Saldos salvos.")
        st.rerun()

elif menu == "IA de Cortes":
    st.title("🧠 IA de Cortes de Gastos")

    sugestoes = gerar_sugestoes_ia(transacoes, provisoes, saldo_total, saldo_previsto)

    for tipo_sugestao, texto in sugestoes:
        if tipo_sugestao == "critico":
            st.error(texto)
        elif tipo_sugestao in ["alerta", "atencao", "previsao"]:
            st.warning(texto)
        elif tipo_sugestao == "corte":
            st.success(texto)
        else:
            st.info(texto)

elif menu == "Históricos":
    st.title("📋 Históricos")

    st.subheader("Transações")
    st.dataframe(transacoes.sort_values("data", ascending=False), use_container_width=True)

    st.subheader("Provisões")
    st.dataframe(provisoes.sort_values("data", ascending=False), use_container_width=True)

    st.subheader("Empréstimos")
    st.dataframe(emprestimos.sort_values("data", ascending=False), use_container_width=True)