---
title: Como usar CDC quando a fonte não tem changelog
date: 2026-11-19
summary: A API da OpenSky só devolve o estado atual das aeronaves. Veja como usei o PostgreSQL como camada de staging para transformar polling em um stream de eventos com Debezium e Kafka.
tags: CDC, Debezium, Kafka, Data Lake, Python
draft: true
---
Change Data Capture costuma ser apresentado assim: você aponta o Debezium para o log de transações de um banco e cada `INSERT`, `UPDATE` e `DELETE` vira um evento. Funciona muito bem quando a fonte **é** um banco de dados.

No meu projeto [OpenSky CDC DataLake](https://github.com/rafaelladuarte/opensky-cdc-datalake) a fonte era outra: uma API REST. E ela não tem log de transações, nem histórico, nem nada que diga *o que mudou*. Este post conta como contornei isso.

## O problema

A [OpenSky Network](https://opensky-network.org/) expõe a posição, a altitude e a velocidade de aeronaves em voo. Só que cada chamada retorna o **estado atual** de todas elas. Se uma aeronave mudou de posição desde a última consulta, a API não avisa: você recebe o novo valor e precisa descobrir a diferença por conta própria.

Isso quebra a premissa do CDC, que depende de um log de mudanças para ler.

## A ideia: criar o log onde ele não existe

Em vez de aplicar CDC na fonte, apliquei na **camada de staging**:

1. Um script Python consulta a API periodicamente.
2. Cada resposta é gravada numa tabela de staging no PostgreSQL, com `INSERT` para aeronaves novas e `UPDATE` para as que já existiam.
3. O Debezium lê o log de transações do PostgreSQL e transforma essas operações em eventos.

Na prática, o *polling* da API passa a gerar as mudanças que o CDC precisa observar. O banco deixa de ser só um destino e vira o gerador do stream de eventos.

> Isso não torna a API "event-driven". A latência continua limitada pela frequência do polling. O que muda é que, daqui para frente, tudo é tratado como um fluxo de eventos.

## A arquitetura

```text
OpenSky API ──polling──▶ PostgreSQL (staging)
                              │  log de transação
                              ▼
                          Debezium
                              │
                              ▼
                        Apache Kafka
                         │         │
              S3 Sink    │         │  consumidor Python (async)
              Connector  ▼         ▼
                   Bronze (JSON)  Silver (Parquet particionado)
                        └── MinIO ──┘
```

O Kafka alimenta duas frentes ao mesmo tempo:

- **Bronze:** um S3 Sink Connector do Kafka Connect grava os eventos crus, em JSON, no MinIO. Nada é alterado, então dá para reprocessar tudo depois.
- **Silver:** um consumidor Python assíncrono lê os mesmos tópicos, remove `NaN`, aplica a tipagem correta e grava arquivos Parquet particionados.

Separar o dado cru do tratado foi uma decisão deliberada: se a regra de limpeza mudar, eu reprocesso a partir da Bronze sem precisar consultar a API de novo.

## Decisões e trade-offs

**Por que PostgreSQL como staging?** O Debezium tem um conector maduro para ele, e o log de transações já entrega exatamente o que eu precisava. <!-- TODO: algum motivo pessoal? já conhecia o Postgres? comparou com outra opção? -->

**Por que duas camadas?** Bronze preserva a fonte da verdade e a Silver entrega dado pronto para consumo. É o padrão medalhão, mas aqui ele também resolve um problema concreto: a API não permite "voltar no tempo".

**Parquet particionado.** Reduz o volume lido em consultas analíticas. <!-- TODO: por qual coluna particionou e por quê? -->

## O que deu trabalho

<!-- TODO: esta seção é a mais valiosa do post. Conte 2 ou 3 problemas reais:
     - configuração do Debezium / Kafka Connect
     - dados com NaN ou tipos inconsistentes vindos da API
     - limites de requisição da OpenSky
     - algo que você faria diferente -->

## Próximos passos

O roadmap do projeto inclui:

- **Apache Iceberg + Trino** para consultas SQL nativas sobre o Data Lake;
- **Apache Superset** para dashboards sobre as camadas Silver e Ouro.

## Conclusão

CDC não exige que a fonte seja um banco. Quando ela não oferece changelog, dá para **criar** um: persistir o estado numa camada intermediária e deixar o log de transações fazer o trabalho de detectar mudanças.

O código completo está no [repositório do projeto](https://github.com/rafaelladuarte/opensky-cdc-datalake).
