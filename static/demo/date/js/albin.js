
function loadSvgIntoContainer(svgUrl, containerId) {
  fetch(svgUrl)
    .then(response => response.text())
    .then(svgContent => {
      const container = document.getElementById(containerId);
      if(container) {
        container.innerHTML = svgContent;
      }
    })
    .catch(error => console.error('Error loading the SVG:', error));
}

// Use the static path to the SVG and the ID of the container
loadSvgIntoContainer('/static/date/svg/albin.svg', 'albin-svg-container');
