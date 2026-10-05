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
});
