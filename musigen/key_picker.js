const KeyPicker = (() => {
  const key = document.getElementById('key');
  const spelling = document.getElementById('keySpelling');
  const field = document.getElementById('spellingField');

  function update() {
    const option = key.selectedOptions[0];
    const names = [option.value, option.dataset.alternate].filter(Boolean);
    spelling.replaceChildren(...names.map(name => {
      const label = name.replace('#','♯').replace('b','♭').replace(' major','장조').replace(' minor','단조');
      return new Option(label, name);
    }));
    field.hidden = names.length === 1;
  }

  key.addEventListener('change', update);
  update();
  return {
    restore(name) {
      const option = Array.from(key.options).find(o => o.value === name || o.dataset.alternate === name);
      if (!option) throw Error('저장된 조성을 확인하세요.');
      key.value = option.value;
      update();
      spelling.value = name;
    }
  };
})();
