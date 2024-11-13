import upath from 'upath';
import fs from 'fs';
import { tmpdir } from 'os';
import toml from 'toml';
import { execSync } from 'child_process';
import { ipcMain } from 'electron';

import { getLogger } from './logger';
import { ipcMainChannels } from './ipcMainChannels';
import { settingsStore } from './settingsStore';

const logger = getLogger(__filename.split('/').slice(-1)[0]);

export function setupAddPlugin() {
  ipcMain.handle(
    ipcMainChannels.ADD_PLUGIN,
    (e, pluginURL) => {
      logger.info('adding plugin at', pluginURL);

      try {
        // Create a temporary directory and check out the plugin's pyproject.toml
        const tmpPluginDir = fs.mkdtempSync(upath.join(tmpdir(), 'natcap-invest-'));
        execSync(
          `git clone --depth 1 --no-checkout ${pluginURL} "${tmpPluginDir}"`,
          { stdio: 'inherit', windowsHide: true }
        );
        execSync('git checkout HEAD pyproject.toml', { cwd: tmpPluginDir, stdio: 'inherit', windowsHide: true });

        // Read in the plugin's pyproject.toml, then delete it
        const pyprojectTOML = toml.parse(fs.readFileSync(
          upath.join(tmpPluginDir, 'pyproject.toml')
        ).toString());
        fs.rmSync(tmpPluginDir, { recursive: true, force: true });

        // Access plugin metadata from the pyproject.toml
        const pluginID = pyprojectTOML.tool.natcap.invest.model_id;

        // Create a conda env containing the plugin and its dependencies
        const envName = `invest_plugin_${pluginID}`;
        const mamba = settingsStore.get('mamba');
      	logger.info(`Plugins: mamba cmd: ${mamba}`);
        let depString = '';
        if (pyprojectTOML.tool.natcap.invest.conda_dependencies) {
          depString = pyprojectTOML.tool.natcap.invest.conda_dependencies.map(
            (dependency) => `"${dependency}"`
          ).join(' ');
        }

        const createInfo = execSync(
          // Always install python, we'll need it to pip install the plugin. Plugins
          // may restrict the version by setting a python requirement in pyproject.toml
          `${mamba} create --yes --name ${envName} -c conda-forge python ${depString}`,
          { windowsHide: true }).toString();
        logger.info(`Plugins: create info:\n${createInfo}`);
        logger.info('Plugins: created mamba env for plugin');
        const runInfo = execSync(
          `${mamba} run --name ${envName} pip install "git+${pluginURL}"`,
          { windowsHide: true }).toString();
        logger.info(`Plugins: run install info:\n${runInfo}`);
        logger.info('Plugins: installed plugin into its env');

        // Write plugin metadata to the workbench's config.json
        const envInfo = execSync(`${mamba} info --envs`, { windowsHide: true }).toString();
        logger.info(`Plugins: env info:\n${envInfo}`);
        const regex = new RegExp(String.raw`^${envName} +(.+)$`, 'm');
        const envPath = envInfo.match(regex)[1];
        logger.info(`Plugins: env path: ${envPath}`);
        logger.info('Plugins: writing plugin info to settings store');
        // Copy over all plugin metadata key/value pairs from the pyproject.toml
        // except for the model_id, because it's the top-level key
        delete pyprojectTOML.tool.natcap.invest.model_id;
        settingsStore.set(
          `plugins.${pluginID}`,
          {
            ...pyprojectTOML.tool.natcap.invest,
            source: pluginURL,
            env: envPath,
          }
        );
        logger.info('Plugins: successfully added plugin');
      } catch (error) {
        logger.info(`Plugins error:\n${error}`);
        logger.info(`Plugins stdError:\n${error.stderr.toString()}`);
        return error;
      }
    }
  );
}

export function setupRemovePlugin() {
  ipcMain.handle(
    ipcMainChannels.REMOVE_PLUGIN,
    (e, pluginID) => {
      logger.info('Plugins: removing plugin', pluginID);
      try {
        // Delete the plugin's conda env
        const env = settingsStore.get(`plugins.${pluginID}.env`);
        const mamba = settingsStore.get('mamba');
      	logger.info('Plugins: mamba cmd', mamba);
        execSync(
          `${mamba} remove --yes --prefix "${env}" --all`,
          { stdio: 'inherit', windowsHide: true }
        );
        // Delete the plugin's data from storage
        settingsStore.delete(`plugins.${pluginID}`);
        logger.info('Plugins: successfully removed plugin');
      } catch (error) {
        logger.info('Plugins: Error removing plugin:');
        logger.info(error);
      }
    }
  );
}
