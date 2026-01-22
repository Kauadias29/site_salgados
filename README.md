 Projeto Site Salgados

## Rotas do sistema

### Rotas públicas (clientes)
- `/` → Página principal (cardápio)
- `/enviar_pedido` → Enviar pedido (POST)

---

## Rotas exclusivas da dona (Admin)
> Somente a dona pode acessar

- `/admin/login` → Página de login
- `/admin/login` (POST) → Envia a senha para entrar
- `/admin` → Painel administrativo
- `/admin/toggle_loja` → Abrir / fechar a loja
- `/admin/logout` → Sair do painel