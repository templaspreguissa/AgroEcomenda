// AgroEncomenda: melhorias progressivas. O site funciona sem JavaScript.
// Fica em arquivo separado por causa da política de segurança de conteúdo (CSP).

document.addEventListener("DOMContentLoaded", () => {
  // Botão "Mostrar" nos campos de senha (ajuda quem digita no celular).
  document.querySelectorAll("input[data-mostrar-senha]").forEach((campo) => {
    const grupo = document.createElement("div");
    grupo.className = "senha-grupo";
    campo.parentNode.insertBefore(grupo, campo);
    grupo.appendChild(campo);

    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "senha-alternar";
    botao.textContent = "Mostrar";
    botao.setAttribute("aria-pressed", "false");
    botao.setAttribute("aria-label", "Mostrar senha");
    grupo.appendChild(botao);

    botao.addEventListener("click", () => {
      const visivel = campo.type === "text";
      campo.type = visivel ? "password" : "text";
      botao.textContent = visivel ? "Mostrar" : "Ocultar";
      botao.setAttribute("aria-pressed", String(!visivel));
      botao.setAttribute("aria-label", visivel ? "Mostrar senha" : "Ocultar senha");
    });
  });

  // Campos específicos por categoria (RF05): mostra só o grupo da categoria escolhida.
  // Sem JavaScript, todos os grupos aparecem e o servidor guarda só os da categoria escolhida.
  document.querySelectorAll("form[data-mapa-categorias]").forEach((formulario) => {
    const mapa = JSON.parse(formulario.dataset.mapaCategorias);
    const seletor = formulario.querySelector("#categoria_id");
    const grupos = formulario.querySelectorAll("fieldset[data-categoria-principal]");
    const atualizar = () => {
      const principal = String(mapa[seletor.value] || "");
      grupos.forEach((grupo) => {
        grupo.hidden = grupo.dataset.categoriaPrincipal !== principal;
      });
    };
    seletor.addEventListener("change", atualizar);
    atualizar();
  });

  // Pede confirmação antes de ações que não podem ser desfeitas (aceitar, recusar, cancelar, retirar).
  document.querySelectorAll("form[data-confirmar]").forEach((formulario) => {
    formulario.addEventListener("submit", (evento) => {
      if (!window.confirm(formulario.dataset.confirmar)) {
        evento.preventDefault();
      }
    });
  });
});
