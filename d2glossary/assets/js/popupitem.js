// popupitem.js
function openPopupItem(id) {
  const trait = traitData[id];
  const props = trait.displayProperties;

  document.getElementById('popupitem-icon').src = "https://www.bungie.net" + props.icon;
  document.getElementById('popupitem-name').textContent = props.name;
  document.getElementById('popupitem-description').textContent = props.description;

  document.getElementById('popupitem').classList.add('show');
  document.body.classList.add('popupitem-open');

  const url = new URL(window.location);
  url.searchParams.set('id', id);
  history.replaceState(null, '', url);

  document.getElementById('popupitem').onclick = (e) => {
    if (e.target.id === 'popupitem') closePopupItem();
  };
}

function closePopupItem() {
  document.getElementById('popupitem').classList.remove('show');
  document.body.classList.remove('popupitem-open');

  const url = new URL(window.location);
  url.searchParams.delete('id');
  history.replaceState(null, '', url);
}

function sharePopupItem() {
  const url = window.location.href;
  navigator.clipboard.writeText(url);
  alert("Lien copié dans le presse-papier :\n" + url);
}
