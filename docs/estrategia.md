# Estratégia — Fase 1

## 1. Justificativa da stack

**Python + DuckDB** como motor OLAP local. O Censo da Educação Superior ultrapassa 450 MB de dados brutos; DuckDB processa esse volume em colunas, em memória/disco local, com alta performance e sem depender de limites de nuvem. As saídas consolidadas são geradas de forma determinística em **Parquet/CSV** na pasta `outputs/`, o que as torna leves, versionáveis e reproduzíveis (os dados brutos ficam fora do Git).

## 2. Camadas de dados

| Camada | Conteúdo | Regras |
|---|---|---|
| **Raw** | Dados oficiais baixados, sem alteração (`data/`, ignorada pelo Git) | Somente leitura |
| **Trusted/Staging** | Limpeza e padronização | Códigos (CO_*) tipados como `string`; tratamento de nulos e valores suprimidos; encoding e delimitadores corretos |
| **Analytical** | Fatos e agregações | Filtrados para Mato Grosso (`CO_UF = 51`); saída em `outputs/` |

## 3. Idempotência

- Scripts de carga parametrizados (ano, UF, caminhos), no padrão **truncate-and-load**.
- Saídas Parquet escritas em arquivo temporário e promovidas por **renomeação atômica**, sobrescrevendo a versão anterior.
- Reexecuções produzem a mesma saída, sem duplicação de registros.

## 4. Armadilhas metodológicas e mitigação

| Armadilha | Mitigação |
|---|---|
| Cursos EAD aparecem em múltiplos polos/locais | Agregação obrigatória por `CO_CURSO` antes de qualquer contagem |
| Planilha de Trajetória com cabeçalho deslocado | Cabeçalhos na **linha 9** (`header`/`skiprows` explícitos) |
| Censo em formato legado | Encoding **latin-1** e delimitador **`;`** |
| Risco de reidentificação | **Supressão de grupos com < 10 alunos** |
| Interpretação indevida dos resultados | Abordagem de **associação estatística**, sem alegação de causalidade |
