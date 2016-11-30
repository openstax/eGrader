var path = require('path');
var webpack = require('webpack');

// Third party plugins
var ManifestRevisionPlugin = require('manifest-revision-webpack-plugin');
var ExtractTextPlugin = require('extract-text-webpack-plugin');

// Development asset host, asset location and build output path.
var publicHost = 'http://localhost:2992';
var rootAssetPath = path.join(__dirname, 'eGrader/static');
var cssAssetPath = path.join(__dirname, 'eGrader/static/css');
var buildOutputPath = path.join(__dirname, 'eGrader/static/build/');

module.exports = {
    context: path.join(__dirname, 'eGrader'),
    entry: {
        app: [
            // 'webpack/hot/dev-server',
            rootAssetPath + '/js/app/main',
            cssAssetPath + '/style',
            cssAssetPath + '/dashboard'
        ],
        exercise_js: [
            rootAssetPath + '/js/app/exerciseViewer'
        ]
    },
    output: {
        path: buildOutputPath,
        publicPath: publicHost + '/',
        filename: '[name].js',
    },
    resolve: {
        extensions: ['', '.js', '.jsx', '.css']
    },
    module: {
        loaders: [
            {
                test: /\.js$/,
                exclude: [/(node_modules)/, /(build)/],
                loader: 'babel',
                query: {
                    presets: ['es2015']
                }
            },
            {
                test: /\.css$/i,
                loader: ExtractTextPlugin.extract('style-loader', 'css-loader')
            },
            {
                test: /\.(jpe?g|png|gif|svg([\?]?.*))$/i,
                loaders: [
                    'file?context=' + rootAssetPath + '&name=[path][name].[hash].[ext]',
                    'image?bypassOnDebug&optimizationLevel=7&interlaced=false'
                ]
            }
        ]
    },
    plugins: [
        new ManifestRevisionPlugin(path.join('eGrader', 'static', 'manifest.json'), {
            rootAssetPath: rootAssetPath,
            ignorePaths: ['.DS_Store', '/css', '/js', '/images', '/pdf', '/build', 'manifest.json']
        }),
        new ExtractTextPlugin('[name].css'),
        new webpack.NoErrorsPlugin()
    ]
};
