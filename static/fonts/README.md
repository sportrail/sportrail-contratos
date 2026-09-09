# Fontes da marca (para o PDF)

`Bebas Neue` (títulos) e `DM Sans` (corpo), ambas SIL Open Font License 1.1 —
licenças em `OFL-BebasNeue.txt` e `OFL-DMSans.txt`.

Estão aqui versionadas, e não instaladas por `apt`, porque nenhuma das duas
existe nos repositórios Debian. O `Dockerfile` copia-as para
`/usr/share/fonts/truetype/sportrail/` e corre `fc-cache`, ficando disponíveis
como fontes de sistema.

Tem de ser assim, e não via `@font-face` a apontar para um ficheiro: o render
isolado (`contract.gerar_pdf_bytes_isolado`) corre com `base_url=None` e só
aceita `data:`, portanto bloquearia qualquer URL de fonte. Como fontes de
sistema, a resolução passa pelo fontconfig/Pango e nunca pelo `url_fetcher` —
o isolamento mantém-se intacto.

Nota: o runner do CI (`.github/workflows/verify.yml`) instala só a lista do
`apt`, não copia estas fontes. Em CI o render cai para DejaVu, o que é
propositado — nenhum teste do `verify.py` afirma nada sobre a família usada.
