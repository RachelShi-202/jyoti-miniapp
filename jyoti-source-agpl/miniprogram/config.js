const cloud = require('./release-config');
module.exports = {
 mode: 'service', transport: 'cloud',
 cloudEnv: cloud.cloudEnv, cloudService: cloud.cloudService,
 localDeveloperLogin: false, membershipEnabled: false,
 annualReportFree: true, version: '0.3.1'
};
