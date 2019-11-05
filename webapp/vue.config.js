var SriPlugin = require('webpack-subresource-integrity');
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  configureWebpack: {
    output: {
      crossOriginLoading: 'anonymous',
    },
    externals: {
      'runtimeConfig': require('./static/runtimeConfig.json')
    },
    plugins: [
      new CopyPlugin([
        { from: 'src/static', to: 'static' }
      ]),
      new SriPlugin({
        hashFuncNames: ['sha256', 'sha384'],
        enabled: true
      }),
    ]
  },
  devServer: {
    https: false
  }
}
