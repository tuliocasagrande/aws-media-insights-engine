  import getRuntimeConfig from '@/static/runtimeConfig.json'

const awsauth = {
    Auth: {
      region: getRuntimeConfig.AWS_REGION,
      userPoolId: getRuntimeConfig.USER_POOL_ID,
      userPoolWebClientId: getRuntimeConfig.USER_POOL_CLIENT_ID,
      identityPoolId: getRuntimeConfig.IDENTITY_POOL_ID
    }
  };

  export default awsauth;
